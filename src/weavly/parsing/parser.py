import json
import shutil
from collections.abc import Collection
from difflib import get_close_matches
from importlib import resources
from pathlib import Path

import typer
from lark import Lark, Token, Transformer, Tree
from lark.exceptions import UnexpectedInput, VisitError

from ..reporting import report_error
from .syntax_errors import describe_syntax_error, terminal_names
from .text import expand_text
from .type_checker import (
    NODE_FUNCTIONS,
    NUMBER_FUNCTIONS,
    Location,
    check_types,
    source_location,
)
from .wvl_transformer import InvalidStringError, WvlTransformer

PARSER_TYPE = "lalr"
ENCODING = "utf-8"
SOURCE_ENCODING = "utf-8-sig"

WVL_SOURCE_EXTENSION = ".wvl"
WVL_BUILD_EXTENSION = ".wvl.json"
WVL_GRAMMAR_FILE = "wvl-grammar.lark"
ENV_BUILD_FILE = "env.json"

# rule -> what its leading ID names, for duplicate errors.
_DECLARATION_KINDS = {
    "number_declaration": "variable",
    "string_declaration": "variable",
    "flag_declaration": "variable",
    "extern_declaration": "variable",
    "pool_declaration": "pool",
    "slot_declaration": "slot",
}
_NODE_KINDS = {"node_start": "node id"}
# declaration type -> env.json list of names.
_NAME_LISTS = {"pool": "pools", "slot": "slots"}
_GOTO_RULES = frozenset({"goto", "inline_goto"})


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
    trees: list[tuple[Path, Tree]] = []
    # name -> location of the first declaration seen with that name.
    declared: dict[str, Location] = {}
    node_ids: dict[str, Location] = {}
    # (kind, node id, location) of every reference to a node.
    node_references: list[tuple[str, str, Location]] = []
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
            tree = _parse_tree(parser, text)
        except UnexpectedInput as e:
            _report_parse_error(e, file, text, names)
            failed = True
            continue
        except InvalidStringError as e:
            _report_string_error(e, file)
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

        # Columns are only in the raw tree.
        _record_unique(
            _id_locations(tree, _DECLARATION_KINDS.keys(), file),
            declared,
            _DECLARATION_KINDS,
            validation_errors,
        )
        _record_unique(
            _id_locations(tree, _NODE_KINDS.keys(), file),
            node_ids,
            _NODE_KINDS,
            validation_errors,
        )
        node_references.extend(
            ("goto", target, location)
            for _, target, location in _id_locations(tree, _GOTO_RULES, file)
        )
        node_references.extend(_call_references(tree, file, validation_errors))
        validation_errors.extend(_number_range_errors(tree, file))
        declarations.extend(data.get("declarations", []))
        trees.append((file, tree))

        outputs.append(
            (out_file, {"source": relative_path.as_posix(), "nodes": data["nodes"]})
        )

    if failed:
        raise typer.Exit(code=1)

    validation_errors.extend(
        (location, f"{kind} target '{target}' matches no node")
        for kind, target, location in node_references
        if target not in node_ids
    )
    variables: dict[str, str] = {}
    for declaration in declarations:
        variables.setdefault(declaration["name"], declaration["type"])
    for file, tree in trees:
        validation_errors.extend(check_types(tree, file, variables))
    if validation_errors:
        for (file, line, column), message in sorted(validation_errors):
            report_error(message, file, line, column)
        raise typer.Exit(code=1)

    file_count = len(outputs)
    outputs.append((Path(ENV_BUILD_FILE), _env(declarations)))
    _replace_build_dir(build_dir, outputs, pretty)
    return file_count


def _env(declarations: list[dict]) -> dict[str, list]:
    env: dict[str, list] = {"declarations": [], "pools": [], "slots": []}
    for declaration in declarations:
        name_list = _NAME_LISTS.get(declaration["type"])
        if name_list is None:
            env["declarations"].append(declaration)
        else:
            env[name_list].append(declaration["name"])
    return env


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
    tree: Tree, rules: Collection[str], file: Path
) -> list[tuple[str, str, Location]]:
    """Return (rule, id, location) for the leading ID of every matching rule, in source order."""
    locations = []
    for subtree in tree.iter_subtrees_topdown():
        if subtree.data in rules:
            id_token = subtree.children[0]
            locations.append(
                (subtree.data, str(id_token), (file, id_token.line, id_token.column))
            )
    return locations


def _call_references(
    tree: Tree, file: Path, errors: list[tuple[Location, str]]
) -> list[tuple[str, str, Location]]:
    """Validate every function call and return the node references of node calls."""
    references = []
    for call in tree.find_data("node_call"):
        function, target = call.children
        if function in NODE_FUNCTIONS:
            references.append((str(function), str(target), source_location(file, target)))
        elif function in NUMBER_FUNCTIONS:
            errors.append(
                (
                    source_location(file, target),
                    f"{function}() takes numbers, not node id '{target}'",
                )
            )
        else:
            errors.append((source_location(file, function), _unknown_function(function)))

    for call in tree.find_data("call"):
        function, arguments = call.children
        count = 0 if arguments is None else len(arguments.children)
        if function in NODE_FUNCTIONS:
            errors.append(
                (source_location(file, function), f"{function}() takes a single node id")
            )
        elif function in NUMBER_FUNCTIONS:
            message = _argument_count_error(function, count)
            if message:
                errors.append((source_location(file, function), message))
        else:
            errors.append((source_location(file, function), _unknown_function(function)))
    return references


def _argument_count_error(function: str, count: int) -> str | None:
    minimum, maximum = NUMBER_FUNCTIONS[function]
    if count >= minimum and (maximum is None or count <= maximum):
        return None
    expected = f"at least {minimum}" if maximum is None else str(minimum)
    noun = "argument" if expected == "1" else "arguments"
    return f"{function}() takes {expected} {noun}, got {count}"


def _unknown_function(function: str) -> str:
    message = f"unknown function '{function}'"
    matches = get_close_matches(function, [*NODE_FUNCTIONS, *NUMBER_FUNCTIONS], n=1)
    if matches:
        message += f", did you mean '{matches[0]}'?"
    return message


def _record_unique(
    locations: list[tuple[str, str, Location]],
    seen: dict[str, Location],
    kinds: dict[str, str],
    errors: list[tuple[Location, str]],
) -> None:
    for rule, name, location in locations:
        if name in seen:
            kind = kinds[rule]
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
    return Lark(
        grammar,
        parser=parser_type,
        propagate_positions=True,
        start=["start", "interpolation"],
    )


def _parse_tree(parser: Lark, text: str) -> Tree:
    tree = parser.parse(text, start="start")
    expand_text(tree, parser)
    return tree


def _parse(parser: Lark, text: str, transformer: Transformer) -> dict:
    tree = _parse_tree(parser, text)
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
