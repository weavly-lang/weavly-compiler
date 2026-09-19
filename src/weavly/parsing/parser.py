import json
import shutil
from importlib import resources
from pathlib import Path

import typer
from lark import Lark, Token, Transformer, Tree
from lark.exceptions import UnexpectedInput, VisitError

from ..reporting import report_error
from .syntax_errors import describe_syntax_error, terminal_names
from .wvl_transformer import InvalidStringError, WvlTransformer

PARSER_TYPE = "lalr"
ENCODING = "utf-8"
SOURCE_ENCODING = "utf-8-sig"

WVL_SOURCE_EXTENSION = ".wvl"
WVL_BUILD_EXTENSION = ".wvl.json"
WVL_GRAMMAR_FILE = "wvl-grammar.lark"
ENV_BUILD_FILE = "env.json"

_DECLARATION_RULES = frozenset(
    {"number_declaration", "string_declaration", "flag_declaration"}
)
_NODE_RULES = frozenset({"node_start"})
_GOTO_RULES = frozenset({"goto", "inline_goto"})

Location = tuple[Path, int, int]


def build_all_files(src_dir: Path, build_dir: Path, pretty: bool) -> int:
    if not src_dir.is_dir():
        report_error(
            f"no '{src_dir.as_posix()}' directory found. Run 'weavly init' to create "
            "a project or run the build from the project root."
        )
        raise typer.Exit(code=1)

    grammar = _load_grammar(WVL_GRAMMAR_FILE)
    parser = _build_parser(grammar, PARSER_TYPE)
    names = terminal_names(parser)
    transformer = WvlTransformer()

    declarations: list[dict] = []
    outputs: list[tuple[Path, dict]] = []
    # name -> location of the first declaration seen with that name.
    declared: dict[str, Location] = {}
    node_ids: dict[str, Location] = {}
    gotos: list[tuple[str, Location]] = []
    validation_errors: list[tuple[Location, str]] = []
    failed = False

    for file in sorted(src_dir.rglob(f"*{WVL_SOURCE_EXTENSION}")):
        if not file.is_file():
            continue

        relative_path = file.relative_to(src_dir)
        out_file = relative_path.with_suffix(WVL_BUILD_EXTENSION)

        try:
            text = file.read_text(encoding=SOURCE_ENCODING)
        except UnicodeDecodeError as e:
            _report_encoding_error(e, file)
            failed = True
            continue

        try:
            tree = parser.parse(text)
        except UnexpectedInput as e:
            _report_parse_error(e, file, text, names)
            failed = True
            continue

        try:
            data = transformer.transform(tree)
        except VisitError as e:
            if not isinstance(e.orig_exc, InvalidStringError):
                raise
            _report_string_error(e.orig_exc, file)
            failed = True
            continue

        # Source locations come from the raw tree; the transformed data has no
        # line numbers.
        _record_unique(
            _id_locations(tree, _DECLARATION_RULES, file),
            declared,
            "variable",
            validation_errors,
        )
        _record_unique(
            _id_locations(tree, _NODE_RULES, file), node_ids, "node id", validation_errors
        )
        gotos.extend(_id_locations(tree, _GOTO_RULES, file))
        validation_errors.extend(_number_range_errors(tree, file))
        declarations.extend(data.get("declarations", []))

        outputs.append((out_file, {"nodes": data["nodes"]}))

    if failed:
        raise typer.Exit(code=1)

    validation_errors.extend(
        (location, f"goto target '{target}' matches no node")
        for target, location in gotos
        if target not in node_ids
    )
    if validation_errors:
        for (file, line, column), message in sorted(validation_errors):
            report_error(message, file, line, column)
        raise typer.Exit(code=1)

    file_count = len(outputs)
    outputs.append((Path(ENV_BUILD_FILE), {"declarations": declarations}))
    _replace_build_dir(build_dir, outputs, pretty)
    return file_count


def _replace_build_dir(
    build_dir: Path, outputs: list[tuple[Path, dict]], pretty: bool
) -> None:
    tmp_dir = build_dir.with_name(f".{build_dir.name}.tmp")
    old_dir = build_dir.with_name(f".{build_dir.name}.old")
    try:
        for leftover in (tmp_dir, old_dir):
            if leftover.exists():
                shutil.rmtree(leftover)
        for out_file, data in outputs:
            _write_json(data, tmp_dir / out_file, pretty)
        if build_dir.exists():
            build_dir.rename(old_dir)
        tmp_dir.rename(build_dir)
    except OSError as e:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        report_error(
            f"could not update '{build_dir.as_posix()}': {e.strerror or e}. "
            "Close any program using its files and build again."
        )
        raise typer.Exit(code=1)
    shutil.rmtree(old_dir, ignore_errors=True)


def _id_locations(
    tree: Tree, rules: frozenset[str], file: Path
) -> list[tuple[str, Location]]:
    """Return (id, location) for the leading ID of every matching rule, in source order."""
    locations = []
    for subtree in tree.iter_subtrees_topdown():
        if subtree.data in rules:
            id_token = subtree.children[0]
            locations.append((str(id_token), (file, id_token.line, id_token.column)))
    return locations


def _record_unique(
    locations: list[tuple[str, Location]],
    seen: dict[str, Location],
    kind: str,
    errors: list[tuple[Location, str]],
) -> None:
    for name, location in locations:
        if name in seen:
            prev_file, prev_line, _ = seen[name]
            errors.append(
                (
                    location,
                    f"duplicate {kind} '{name}', first declared at "
                    f"{prev_file.as_posix()}:{prev_line}",
                )
            )
        else:
            seen[name] = location


def _number_range_errors(tree: Tree, file: Path) -> list[tuple[Location, str]]:
    errors = []
    for declaration in tree.find_data("number_declaration"):
        name_token, *numbers = declaration.children
        minimum, maximum, value = (_number(child) for child in numbers)
        location = (file, name_token.line, name_token.column)
        name = str(name_token)

        if minimum is not None and maximum is not None and minimum > maximum:
            errors.append(
                (location, f"number '{name}' has min {minimum:g} greater than max {maximum:g}")
            )
            continue

        default = f"default {value:g}" if value is not None else "implicit default 0"
        value = value or 0.0
        if minimum is not None and value < minimum:
            errors.append(
                (location, f"number '{name}' has {default} below its min {minimum:g}")
            )
        elif maximum is not None and value > maximum:
            errors.append(
                (location, f"number '{name}' has {default} above its max {maximum:g}")
            )
    return errors


def _number(child: Tree | Token | None) -> float | None:
    if child is None:
        return None
    if isinstance(child, Tree):
        return -float(child.children[0])
    return float(child)


def _write_json(data: dict, out_file: Path, pretty: bool) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        out_file.write_text(json.dumps(data, indent=2), encoding=ENCODING)
    else:
        out_file.write_text(json.dumps(data, separators=(",", ":")), encoding=ENCODING)


def _load_grammar(grammar_file: str) -> str:
    grammar = (
        resources.files("weavly.resources")
        .joinpath(grammar_file)
        .read_text(encoding=ENCODING)
    )
    return grammar


def _build_parser(grammar: str, parser_type: str) -> Lark:
    return Lark(grammar, parser=parser_type)


def _parse(parser: Lark, text: str, transformer: Transformer) -> dict:
    tree = parser.parse(text)
    data = transformer.transform(tree)
    return data


def _report_encoding_error(error: UnicodeDecodeError, file: Path) -> None:
    line = error.object[: error.start].count(b"\n") + 1
    report_error("invalid encoding, files must be saved as UTF-8", file, line)


def _report_string_error(error: InvalidStringError, file: Path) -> None:
    token = error.token
    report_error(
        f"invalid string {token.value}: {error.reason}", file, token.line, token.column
    )


def _report_parse_error(
    error: UnexpectedInput, file: Path, text: str, names: dict[str, str]
) -> None:
    message, details = describe_syntax_error(error, text, names)
    report_error(message, file, error.line, error.column, details)
