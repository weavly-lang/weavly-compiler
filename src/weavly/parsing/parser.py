import json
import shutil
from importlib import resources
from pathlib import Path

import typer
from lark import Lark, Transformer
from lark.exceptions import UnexpectedCharacters, UnexpectedInput, UnexpectedToken

from .env_transformer import EnvTransformer
from .json_transformer import JsonTransformer

PARSER_TYPE = "lalr"
ENCODING = "utf-8"

SOURCE_FILE_EXTENSION = ".wvl"
BUILD_FILE_EXTENSION = ".wvl.json"
ENV_SOURCE_FILE_EXTENSION = ".wenvl"
ENV_BUILD_FILE_EXTENSION = ".wenvl.json"


def build_all_files(src_dir: Path, build_dir: Path, pretty: bool) -> None:
    if build_dir.exists():
        shutil.rmtree(build_dir)
    
    _build_files_with_extension(
        src_dir, 
        build_dir, 
        pretty, 
        SOURCE_FILE_EXTENSION, 
        BUILD_FILE_EXTENSION,
        "grammar.lark", 
        JsonTransformer()
    )

    _build_files_with_extension(
        src_dir, 
        build_dir, 
        pretty, 
        ENV_SOURCE_FILE_EXTENSION, 
        ENV_BUILD_FILE_EXTENSION,
        "env-grammar.lark", 
        EnvTransformer()
    )


def _build_files_with_extension(
    src_dir: Path, 
    build_dir: Path, 
    pretty: bool, 
    source_extension: str,
    build_extension: str,
    grammar_file: str, 
    transformer: Transformer
) -> None:
    grammar = _load_grammar(grammar_file)
    parser = _build_parser(grammar, PARSER_TYPE)

    for file in src_dir.rglob(f"*{source_extension}"):
        if not file.is_file():
            continue

        relative_path = file.relative_to(src_dir)
        out_file = (build_dir / relative_path).with_suffix(f"{build_extension}")
        out_file.parent.mkdir(parents=True, exist_ok=True)

        text = file.read_text(encoding=ENCODING)

        try:
            data = _parse(parser, text, transformer)
        except UnexpectedInput as e:
            _format_parse_error(e, file)
            raise typer.Exit(code=1)

        if pretty:
            out_file.write_text(json.dumps(data, indent=2), encoding=ENCODING)
        else:
            out_file.write_text(
                json.dumps(data, separators=(",", ":")), encoding=ENCODING
            )


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


def _format_parse_error(error: UnexpectedInput, file: Path) -> None:
    """Format and display a concise parse error message."""
    typer.echo()
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
    if error.expected:
        typer.secho("  Expected one of:", fg=typer.colors.CYAN, err=True)
        for expected in sorted(error.expected):
            typer.secho(f"    * {expected}", fg=typer.colors.GREEN, err=True)
        typer.echo("", err=True)

    # Show previous tokens if available
    if hasattr(error, "previous_tokens") and error.previous_tokens:
        typer.secho(
            "  Previous tokens: ", nl=False, fg=typer.colors.BRIGHT_BLACK, err=True
        )
        typer.secho(f"{error.previous_tokens}", fg=typer.colors.BRIGHT_BLACK, err=True)
        typer.echo("", err=True)
