from pathlib import Path

import typer

from .parsing import (
    WVL_SOURCE_EXTENSION,
    build_all_files,
)

SOURCE_DIR = Path("src")
BUILD_DIR = Path("build")

NODE_INIT_STRING = (
    "@env\n"
    "name: string = \"World\"\n"
    "@endenv\n"
    "\n"
    "@node first_node\n"
    "Hello $name!\n"
    "@endnode\n"
)

app = typer.Typer()


@app.command()
def build(pretty: bool = False):
    build_all_files(SOURCE_DIR, BUILD_DIR, pretty)


@app.command()
def init(name: str = typer.Argument(None)):
    if name:
        base = Path(name)
        if base.exists():
            typer.echo(f"Project '{name}' already exists")
            raise typer.Exit(code=1)
        base.mkdir()
    else:
        base = Path.cwd()

    src: Path = base / "src"
    if src.exists():
        typer.echo(f"Directory '{src}' already exists")
        raise typer.Exit(code=1)
    src.mkdir()
    (src / f"nodes{WVL_SOURCE_EXTENSION}").write_text(
        NODE_INIT_STRING, encoding="utf-8"
    )
