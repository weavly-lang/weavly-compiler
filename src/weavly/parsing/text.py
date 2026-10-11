import json
import re
from typing import NamedTuple

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput
from lark.tree import Meta

_TEXT_UNIT = re.compile(r"\\[{:]|.", re.DOTALL)
_QUOTED_UNIT = re.compile(
    r"\\u[dD][89abAB][0-9a-fA-F]{2}\\u[dD][c-fC-F][0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}|\\.|.",
    re.DOTALL,
)
_QUOTED = ("STRING", "QUOTED_SPEAKER")
_STRING = re.compile(r'"(?:\\.|[^"\\])*"')
# A narration line looks like dialogue if a colon ends one of its first words.
_DIALOGUE_WORDS = 3


class _Char(NamedTuple):
    char: str
    # Offset in the raw token.
    offset: int
    # Written as an escape, so never a brace that opens or closes an interpolation.
    escaped: bool


class InvalidStringError(ValueError):
    def __init__(self, token: Token, reason: str) -> None:
        super().__init__(reason)
        self.token = token
        self.reason = reason


class UnclosedInterpolationError(UnexpectedInput):
    def __init__(self, line: int, column: int) -> None:
        super().__init__("unclosed '{' in text")
        self.line = line
        self.column = column


class BraceInDefaultError(UnexpectedInput):
    def __init__(self, line: int, column: int) -> None:
        super().__init__("unexpected '{' in a default")
        self.line = line
        self.column = column


def source_lines(text: str) -> list[str]:
    """Split `text` into lines at newlines only, as the parser counts them."""
    return [line.removesuffix("\r") for line in text.split("\n")]


def blank_strings(line: str) -> str:
    """Replace every quoted string in `line` with spaces, keeping the columns of the rest."""
    return _STRING.sub(lambda string: " " * len(string.group()), line)


def expand_text(tree: Tree, parser: Lark) -> None:
    """Replace each line's text with a `text` tree and each quoted string with a `string` or
    `interpolated` tree, made of plain strings and interpolations.

    A narration line also gets the colon that makes it look like dialogue, or None.
    """
    for subtree in tree.iter_subtrees():
        narration = subtree.data == "narration_line"
        colon = _dialogue_colon(subtree.children[0]) if narration else None
        subtree.children = [
            _text(child, parser, subtree.data == "string_value")
            if isinstance(child, Token) and child.type in ("TEXT", *_QUOTED)
            else child
            for child in subtree.children
        ]
        if narration:
            subtree.children.append(colon)


def _dialogue_colon(token: Token) -> Token | None:
    """Return the first unescaped colon followed by whitespace or the end that ends one of the
    first words of `token`, an interpolation counting as part of a word."""
    chars = _chars(token)
    words = 0
    i = 0
    while i < len(chars) and words < _DIALOGUE_WORDS:
        if chars[i].char.isspace():
            i += 1
            continue
        words += 1
        while i < len(chars) and not chars[i].char.isspace():
            char = chars[i]
            if char.char == "{" and not char.escaped:
                i = (_closing_brace(chars, i) or len(chars)) + 1
                continue
            ends_word = i + 1 == len(chars) or chars[i + 1].char.isspace()
            if char.char == ":" and not char.escaped and ends_word:
                return Token("COLON", ":", line=token.line, column=token.column + char.offset)
            i += 1
    return None


def _text(token: Token, parser: Lark, constant: bool) -> Tree:
    chars = _chars(token)
    segments: list[str | Tree] = []
    plain: list[str] = []
    i = 0
    while i < len(chars):
        if chars[i].char != "{" or chars[i].escaped:
            plain.append(chars[i].char)
            i += 1
            continue
        if constant:
            raise BraceInDefaultError(token.line, token.column + chars[i].offset)
        end = _closing_brace(chars, i)
        if end is None:
            raise UnclosedInterpolationError(token.line, token.column + chars[i].offset)
        if plain:
            segments.append("".join(plain))
            plain = []
        segments.append(_interpolation(chars[i : end + 1], token, parser))
        i = end + 1
    if plain:
        segments.append("".join(plain))
    meta = Meta()
    meta.empty = False
    meta.line, meta.column = token.line, token.column
    meta.end_line, meta.end_column = token.end_line, token.end_column
    if token.type == "TEXT":
        return Tree("text", segments, meta)
    if all(isinstance(segment, str) for segment in segments):
        return Tree("string", segments, meta)
    return Tree("interpolated", segments, meta)


def _chars(token: Token) -> list[_Char]:
    raw = token.value
    if token.type in _QUOTED:
        pattern, start, end = _QUOTED_UNIT, 1, len(raw) - 1
    else:
        pattern, start, end = _TEXT_UNIT, len(raw) - len(raw.lstrip()), len(raw.rstrip())

    chars = []
    for match in pattern.finditer(raw, start, end):
        unit = match.group()
        if unit == "\\{" or (unit == "\\:" and token.type == "TEXT"):
            chars.append(_Char(unit[1], match.start(), True))
        elif len(unit) == 1:
            chars.append(_Char(unit, match.start(), False))
        else:
            chars.append(_Char(_unescape(unit, token), match.start(), True))
    return chars


def _unescape(unit: str, token: Token) -> str:
    try:
        return json.loads(f'"{unit}"')
    except json.JSONDecodeError as e:
        raise InvalidStringError(token, e.msg) from e


def _closing_brace(chars: list[_Char], start: int) -> int | None:
    in_string = False
    i = start + 1
    while i < len(chars):
        char = chars[i].char
        if in_string and char == "\\":
            i += 1
        elif char == '"':
            in_string = not in_string
        elif char == "}" and not in_string and not chars[i].escaped:
            return i
        i += 1
    return None


def _interpolation(chars: list[_Char], token: Token, parser: Lark) -> Tree:
    offsets = [char.offset for char in chars]
    offsets.append(offsets[-1] + 1)

    def column(relative: int) -> int:
        return token.column + offsets[relative - 1]

    try:
        tree = parser.parse("".join(char.char for char in chars), start="interpolation")
        expand_text(tree, parser)
    except UnexpectedInput as e:
        e.line = token.line
        e.column = column(e.column)
        raise
    except InvalidStringError as e:
        e.token.line = token.line
        e.token.column = column(e.token.column)
        raise

    for subtree in tree.iter_subtrees():
        meta = subtree.meta
        if not meta.empty:
            meta.line = meta.end_line = token.line
            meta.column, meta.end_column = column(meta.column), column(meta.end_column)
    for leaf in tree.scan_values(lambda value: isinstance(value, Token)):
        leaf.line = leaf.end_line = token.line
        leaf.column, leaf.end_column = column(leaf.column), column(leaf.end_column)
    return tree
