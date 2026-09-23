import re

from lark import Lark, Token
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken
from lark.lexer import PatternStr

END = "$END"

PATTERN_NAMES = {
    "NUMBER": "a number",
    "STRING": "a quoted string",
    "ID": "a name",
    "TEXT": "text",
    "CHARACTER_NAME": "a character name",
    "COMP_OP": "a comparison operator",
    "MATCH_MODIFIER": "'first', 'last' or 'all'",
    "_COMMAND": "a @command",
    "_NEWLINE": "end of line",
    "COMMENT": "a comment",
    "WS_INLINE": "whitespace",
}

_BLOCKS = {
    "@node": "@endnode",
    "@env": "@endenv",
    "@if": "@endif",
    "@options": "@endoptions",
    "@random": "@endrandom",
    "@match": "@endmatch",
}
_OPENERS = {closer: opener for opener, closer in _BLOCKS.items()}
_PARENTS = {
    "@option": "@options",
    "@hint": "@options",
    "@case": "@random",
    "@when": "@match",
    "@elif": "@if",
    "@else": "@if",
}
_KEYWORD = re.compile(r"\s*(@\w+)")
_COMMAND_START = re.compile(r"\s*@(\w+)\s*")
_MAX_TOKEN_LENGTH = 40


def terminal_names(parser: Lark) -> dict[str, str]:
    names = {END: "end of file"}
    for terminal in parser.terminals:
        if isinstance(terminal.pattern, PatternStr):
            names[terminal.name] = f"'{terminal.pattern.value}'"
        else:
            names[terminal.name] = PATTERN_NAMES.get(terminal.name, terminal.name)
    return names


def describe_syntax_error(
    error: UnexpectedInput, text: str, names: dict[str, str]
) -> tuple[str, list[str]]:
    lines = text.splitlines()
    details = _excerpt(lines, error.line, error.column)

    if isinstance(error, UnexpectedToken):
        message = f"unexpected {_describe_token(error.token, names)}"
        hint = _block_hint(error.token, lines, error.line) or _command_hint(
            error.token, lines, error.line, names
        )
    elif isinstance(error, UnexpectedCharacters):
        message = f"unexpected character {error.char!r}"
        hint = None
    else:
        return "syntax error", details

    if hint:
        details.append(f"hint: {hint}")
    else:
        expected = (
            getattr(error, "accepts", None)
            or getattr(error, "expected", None)
            or getattr(error, "allowed", None)
        )
        if expected:
            details.append(_expected(sorted({names.get(n, n) for n in expected})))
    return message, details


def _describe_token(token: Token, names: dict[str, str]) -> str:
    if token.type in (END, "_NEWLINE"):
        return names[token.type]
    value = str(token.value).strip()
    if token.type == "TEXT":
        value = value.split()[0]
    if len(value) > _MAX_TOKEN_LENGTH:
        value = value[:_MAX_TOKEN_LENGTH] + "..."
    return f"'{value}'"


def _expected(names: list[str]) -> str:
    if len(names) == 1:
        return f"expected {names[0]}"
    return f"expected one of: {', '.join(names)}"


def _excerpt(lines: list[str], line: int, column: int) -> list[str]:
    if not 1 <= line <= len(lines):
        return []
    source = lines[line - 1]
    gutter = str(line)
    pad = "".join("\t" if char == "\t" else " " for char in source[: column - 1])
    return [f"{gutter} | {source}", f"{' ' * len(gutter)} | {pad}^"]


def _block_hint(token: Token, lines: list[str], line: int) -> str | None:
    if token.type == END:
        stack = _open_blocks(lines)
        if not stack:
            return None
        opener, opened_at = stack[-1]
        return f"the {opener} block opened at line {opened_at} is missing its {_BLOCKS[opener]}"

    keyword = str(token.value).strip()
    stack = _open_blocks(lines[: line - 1])
    if keyword in _PARENTS:
        parent = _PARENTS[keyword]
        if not stack or stack[-1][0] != parent:
            return f"{keyword} can only be used inside an {parent} block"
        return None
    if keyword not in _OPENERS:
        return None
    closer = keyword
    opener = _OPENERS[closer]
    if all(open_block != opener for open_block, _ in stack):
        return f"there is no open {opener} block for {closer} to close"
    top, opened_at = stack[-1]
    if top != opener:
        return (
            f"the {top} block opened at line {opened_at} must be closed with "
            f"{_BLOCKS[top]} first"
        )
    return None


def _command_hint(
    token: Token, lines: list[str], line: int, names: dict[str, str]
) -> str | None:
    # The lexer can read the colon and the rest of the line as one TEXT token.
    if not str(token.value).lstrip().startswith(":") or not 1 <= line <= len(lines):
        return None
    source = lines[line - 1]
    match = _COMMAND_START.fullmatch(source[: token.column - 1])
    if not match or f"'@{match.group(1)}'" in names.values():
        return None
    rest = source[token.column - 1 :].strip()[1:].strip()
    example = rest.replace('"', '\\"') or "text"
    return f'command arguments are expressions, like @{match.group(1)} "{example}"'


def _open_blocks(lines: list[str]) -> list[tuple[str, int]]:
    stack: list[tuple[str, int]] = []
    for number, source in enumerate(lines, start=1):
        match = _KEYWORD.match(source)
        if not match:
            continue
        keyword = match.group(1)
        if keyword in _BLOCKS:
            stack.append((keyword, number))
        elif keyword in _OPENERS and stack and stack[-1][0] == _OPENERS[keyword]:
            stack.pop()
    return stack
