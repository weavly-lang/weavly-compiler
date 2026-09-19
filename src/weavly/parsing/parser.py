import json
import shutil
from importlib import resources
from pathlib import Path

import typer
from lark import Lark, Transformer, Tree
from lark.exceptions import (
    UnexpectedCharacters,
    UnexpectedInput,
    UnexpectedToken,
    VisitError,
)

from .wvl_transformer import InvalidStringError, WvlTransformer

PARSER_TYPE = "lalr"
ENCODING = "utf-8"

WVL_SOURCE_EXTENSION = ".wvl"
WVL_BUILD_EXTENSION = ".wvl.json"
WVL_GRAMMAR_FILE = "wvl-grammar.lark"
ENV_BUILD_FILE = "env.json"

_DECLARATION_RULES = frozenset(
    {"number_declaration", "string_declaration", "flag_declaration"}
)
_NODE_RULES = frozenset({"node_start"})
_GOTO_RULES = frozenset({"goto", "inline_goto"})


def build_all_files(src_dir: Path, build_dir: Path, pretty: bool) -> None:
    if not src_dir.is_dir():
        typer.secho(
            f"No '{src_dir}' directory found. Run 'weavly init' to create a project "
            "or run the build from the project root.",
            fg=typer.colors.RED,
            bold=True,
            err=True,
        )
        raise typer.Exit(code=1)

    grammar = _load_grammar(WVL_GRAMMAR_FILE)
    parser = _build_parser(grammar, PARSER_TYPE)
    transformer = WvlTransformer()

    declarations: list[dict] = []
    outputs: list[tuple[Path, dict]] = []
    # name -> (file, line) of the first declaration seen with that name.
    declared: dict[str, tuple[Path, int]] = {}
    duplicate_declarations: list[str] = []
    node_ids: dict[str, tuple[Path, int]] = {}
    duplicate_nodes: list[str] = []
    gotos: list[tuple[str, Path, int]] = []

    for file in sorted(src_dir.rglob(f"*{WVL_SOURCE_EXTENSION}")):
        if not file.is_file():
            continue

        relative_path = file.relative_to(src_dir)
        out_file = relative_path.with_suffix(WVL_BUILD_EXTENSION)

        text = file.read_text(encoding=ENCODING)

        try:
            tree = parser.parse(text)
        except UnexpectedInput as e:
            _format_parse_error(e, file)
            raise typer.Exit(code=1)

        # Collect declaration source locations from the raw tree (tokens carry
        # line numbers) before the transform discards them.
        _record_unique(
            _id_locations(tree, _DECLARATION_RULES), file, declared, duplicate_declarations
        )
        _record_unique(_id_locations(tree, _NODE_RULES), file, node_ids, duplicate_nodes)
        gotos.extend(
            (target, file, line) for target, line in _id_locations(tree, _GOTO_RULES)
        )

        try:
            data = transformer.transform(tree)
        except VisitError as e:
            if not isinstance(e.orig_exc, InvalidStringError):
                raise
            _format_string_error(e.orig_exc, file)
            raise typer.Exit(code=1)
        declarations.extend(data.get("declarations", []))

        outputs.append((out_file, {"nodes": data["nodes"]}))

    unresolved_gotos = [
        f"  '{target}' at {file}:{line}"
        for target, file, line in gotos
        if target not in node_ids
    ]

    errors = {
        "Duplicate variable declarations:": duplicate_declarations,
        "Duplicate node ids:": duplicate_nodes,
        "Goto targets with no matching node:": unresolved_gotos,
    }
    if any(errors.values()):
        for header, lines in errors.items():
            if not lines:
                continue
            typer.secho(header, fg=typer.colors.RED, bold=True, err=True)
            for line in lines:
                typer.secho(line, fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    outputs.append((Path(ENV_BUILD_FILE), {"declarations": declarations}))
    _replace_build_dir(build_dir, outputs, pretty)


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
        typer.secho(
            f"Could not update '{build_dir}': {e.strerror or e}. "
            "Close any program using its files and build again.",
            fg=typer.colors.RED,
            bold=True,
            err=True,
        )
        raise typer.Exit(code=1)
    shutil.rmtree(old_dir, ignore_errors=True)


def _id_locations(tree: Tree, rules: frozenset[str]) -> list[tuple[str, int]]:
    """Return (id, line) for the leading ID of every matching rule, in source order."""
    locations = []
    for subtree in tree.iter_subtrees_topdown():
        if subtree.data in rules:
            id_token = subtree.children[0]
            locations.append((str(id_token), id_token.line))
    return locations


def _record_unique(
    locations: list[tuple[str, int]],
    file: Path,
    seen: dict[str, tuple[Path, int]],
    duplicates: list[str],
) -> None:
    for name, line in locations:
        if name in seen:
            prev_file, prev_line = seen[name]
            duplicates.append(
                f"  '{name}' declared at {prev_file}:{prev_line} "
                f"and again at {file}:{line}"
            )
        else:
            seen[name] = (file, line)


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


def _format_string_error(error: InvalidStringError, file: Path) -> None:
    """Report a string literal whose escapes cannot be decoded."""
    token = error.token
    typer.secho(
        f"Invalid string in file: {file}, Line {token.line}, Column {token.column}",
        fg=typer.colors.RED,
        bold=True,
        err=True,
    )
    typer.secho(f"  {token.value}", fg=typer.colors.MAGENTA, err=True)
    typer.secho(f"  {error.reason}", fg=typer.colors.RED, err=True)


def _format_parse_error(error: UnexpectedInput, file: Path) -> None:
    """Format and display a concise parse error message."""
    typer.echo(err=True)
    typer.secho(
        f"Syntax Error in file: {file}, Line {error.line}, Column {error.column}",
        fg=typer.colors.RED,
        bold=True,
        err=True,
    )
    typer.echo("", err=True)

    # Show the error type and unexpected token
    if isinstance(error, UnexpectedToken):
        token = error.token
        typer.secho("  Unexpected token: ", nl=False, fg=typer.colors.RED, err=True)
        typer.secho(
            f"{token.type!r}", nl=False, fg=typer.colors.MAGENTA, bold=True, err=True
        )
        typer.secho(" = ", nl=False, err=True)
        typer.secho(f"{token.value!r}", fg=typer.colors.BRIGHT_WHITE, err=True)
    elif isinstance(error, UnexpectedCharacters):
        typer.secho(
            "  Unexpected character(s): ", nl=False, fg=typer.colors.RED, err=True
        )
        typer.secho(f"{error.char!r}", fg=typer.colors.MAGENTA, bold=True, err=True)
    else:
        typer.secho(f"  {error.__class__.__name__}", fg=typer.colors.RED, err=True)

    typer.echo("", err=True)

    # Show what was expected
    expected_terminals = getattr(error, "expected", None) or getattr(
        error, "allowed", None
    )
    if expected_terminals:
        typer.secho("  Expected one of:", fg=typer.colors.CYAN, err=True)
        for expected in sorted(expected_terminals):
            typer.secho(f"    * {expected}", fg=typer.colors.GREEN, err=True)
        typer.echo("", err=True)

    # Show previous tokens if available
    if hasattr(error, "previous_tokens") and error.previous_tokens:
        typer.secho(
            "  Previous tokens: ", nl=False, fg=typer.colors.BRIGHT_BLACK, err=True
        )
        typer.secho(f"{error.previous_tokens}", fg=typer.colors.BRIGHT_BLACK, err=True)
        typer.echo("", err=True)
