import json
import re

from lark import Lark, Token, Tree
from lark.exceptions import UnexpectedInput

from .wvl_transformer import InvalidStringError

_TEXT_RULES = frozenset(
    {
        "narration_line",
        "character_line",
        "named_character_line",
        "option",
        "hint_option",
        "continue_",
    }
)
_TEXT_TOKENS = frozenset({"TEXT", "STRING"})
_TEXT_UNIT = re.compile(r"\\\{|.", re.DOTALL)
_QUOTED_UNIT = re.compile(
    r"\\u[dD][89abAB][0-9a-fA-F]{2}\\u[dD][c-fC-F][0-9a-fA-F]{2}|\\u[0-9a-fA-F]{4}|\\.|.",
    re.DOTALL,
)

# (character, offset in the raw token, written as \{)
_Char = tuple[str, int, bool]


class UnclosedInterpolationError(UnexpectedInput):
    def __init__(self, line: int, column: int) -> None:
        super().__init__("unclosed '{' in text")
        self.line = line
        self.column = column


def expand_text(tree: Tree, parser: Lark) -> None:
    """Replace each text token with a `text` tree of plain strings and interpolations."""
    for subtree in tree.iter_subtrees():
        if subtree.data in _TEXT_RULES:
            subtree.children = [
                _text(child, parser)
                if isinstance(child, Token) and child.type in _TEXT_TOKENS
                else child
                for child in subtree.children
            ]


def _text(token: Token, parser: Lark) -> Tree:
    chars = _chars(token)
    segments: list[str | Tree] = []
    plain: list[str] = []
    i = 0
    while i < len(chars):
        char, offset, escaped = chars[i]
        if char != "{" or escaped:
            plain.append(char)
            i += 1
            continue
        end = _closing_brace(chars, i)
        if end is None:
            raise UnclosedInterpolationError(token.line, token.column + offset)
        if plain:
            segments.append("".join(plain))
            plain = []
        segments.append(_interpolation(chars[i : end + 1], token, parser))
        i = end + 1
    if plain:
        segments.append("".join(plain))
    return Tree("text", segments)


def _chars(token: Token) -> list[_Char]:
    raw = token.value
    if token.type == "STRING":
        pattern, start, end = _QUOTED_UNIT, 1, len(raw) - 1
    else:
        pattern, start, end = _TEXT_UNIT, len(raw) - len(raw.lstrip()), len(raw)

    chars = []
    for match in pattern.finditer(raw, start, end):
        unit = match.group()
        if unit == "\\{":
            chars.append(("{", match.start(), True))
        elif len(unit) == 1:
            chars.append((unit, match.start(), False))
        else:
            chars.append((_unescape(unit, token), match.start(), False))
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
        char = chars[i][0]
        if in_string and char == "\\":
            i += 1
        elif char == '"':
            in_string = not in_string
        elif char == "}" and not in_string:
            return i
        i += 1
    return None


def _interpolation(chars: list[_Char], token: Token, parser: Lark) -> Tree:
    offsets = [offset for _, offset, _ in chars]
    offsets.append(offsets[-1] + 1)

    def column(relative: int) -> int:
        return token.column + offsets[relative - 1]

    try:
        tree = parser.parse("".join(char for char, _, _ in chars), start="interpolation")
    except UnexpectedInput as e:
        e.line = token.line
        e.column = column(e.column)
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
