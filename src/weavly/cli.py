from importlib.metadata import version as package_version
from pathlib import Path

import typer

from .parsing import (
    WVL_SOURCE_EXTENSION,
    build_all_files,
)
from .reporting import report_error

SOURCE_DIR = Path("src")
BUILD_DIR = Path("build")

NODE_INIT_STRING = (
    "@env\n"
    "name: string = \"World\"\n"
    "@endenv\n"
    "\n"
    "@node first_node\n"
    "Hello {$name}!\n"
    "@endnode\n"
)

app = typer.Typer(add_completion=False, pretty_exceptions_show_locals=False)


def _print_version(value: bool) -> None:
    if value:
        typer.echo(f"weavly {package_version('weavly')}")
        raise typer.Exit()


@app.callback()
def main(
    version: bool = typer.Option(
        False,
        "--version",
        callback=_print_version,
        is_eager=True,
        help="Show the version and exit.",
    ),
):
    """Compiler for the Weavly dialogue scripting language."""


@app.command()
def build(
    pretty: bool = typer.Option(
        False, "--pretty", help="Write indented, human-readable JSON."
    ),
):
    """Compile src/**/*.wvl into build/."""
    count = build_all_files(SOURCE_DIR, BUILD_DIR, pretty)
    files = "file" if count == 1 else "files"
    typer.echo(f"Built {count} {files} into {BUILD_DIR.as_posix()}/")


@app.command()
def init(
    name: str = typer.Argument(
        None, help="Directory to create. Defaults to the current directory."
    ),
):
    """Create a new Weavly project with a starter src/nodes.wvl."""
    if name:
        base = Path(name)
        if base.exists():
            report_error(f"project '{name}' already exists")
            raise typer.Exit(code=1)
        base.mkdir(parents=True)
    else:
        base = Path()

    src: Path = base / "src"
    if src.exists():
        report_error(f"directory '{src.as_posix()}' already exists")
        raise typer.Exit(code=1)
    src.mkdir()
    nodes_file = src / f"nodes{WVL_SOURCE_EXTENSION}"
    nodes_file.write_text(NODE_INIT_STRING, encoding="utf-8")
    typer.echo(f"Created {nodes_file.as_posix()}")
