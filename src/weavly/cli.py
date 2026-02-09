import json
import time
from pathlib import Path

import typer
from watchdog.observers import Observer

from .parsing import (
    WVL_BUILD_EXTENSION,
    WVL_SOURCE_EXTENSION,
    FileHandler,
    build_all_files,
)
from .runtime import Context, Node, compile_nodes

SOURCE_DIR = Path("src")
BUILD_DIR = Path("build")

NODE_INIT_STRING = "@node first_node\nHello World!\n@endnode"

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
    src.mkdir()
    (src / f"nodes{WVL_SOURCE_EXTENSION}").write_text(
        NODE_INIT_STRING, encoding="utf-8"
    )


@app.command()
def run(name: str = typer.Argument(None), debug: bool = False):
    if not SOURCE_DIR.exists():
        typer.secho(
            f"Error: Source directory '{SOURCE_DIR}' not found",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    build_all_files(SOURCE_DIR, BUILD_DIR, False)

    if not BUILD_DIR.exists():
        typer.secho(
            f"Error: Build directory '{BUILD_DIR}' was not created",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    nodes: list[Node] = []
    context: Context = Context(debug)

    build_files_found = False
    for file in BUILD_DIR.rglob(f"*{WVL_BUILD_EXTENSION}"):
        build_files_found = True
        try:
            with open(file, "r", encoding="utf-8") as f:
                data = json.load(f)
            nodes.extend(compile_nodes(data))
        except json.JSONDecodeError as e:
            typer.secho(
                f"Error: Invalid JSON in '{file}': {e}", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(code=1)
        except Exception as e:
            typer.secho(
                f"Error: Failed to compile '{file}': {e}", fg=typer.colors.RED, err=True
            )
            raise typer.Exit(code=1)

    if not build_files_found:
        typer.secho(
            f"Error: No build files found in '{BUILD_DIR}'",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    if not nodes:
        typer.secho(
            "Error: No nodes were compiled from build files",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    for node in nodes:
        context.nodes.add(node)

    if not name:
        name = nodes[0].id

    # Validate that the requested node exists
    if not any(node.id == name for node in nodes):
        available_nodes = ", ".join([node.id for node in nodes])
        typer.secho(
            f"Error: Node '{name}' not found. Available nodes: {available_nodes}",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(code=1)

    try:
        context.run_dialog(name)
    except Exception as e:
        typer.secho(f"\nRuntime error: {e}", fg=typer.colors.RED, err=True)
        if debug:
            import traceback

            traceback.print_exc()
        raise typer.Exit(code=1)


@app.command()
def watch(pretty: bool = False):
    """Watch src directory and rebuild on changes."""

    if not SOURCE_DIR.exists():
        typer.secho("Error: 'src' directory not found", fg=typer.colors.RED, err=True)
        raise typer.Exit(code=1)

    # Initial build
    typer.echo("Initial build...")
    try:
        build_all_files(SOURCE_DIR, BUILD_DIR, pretty)
        typer.secho("Build successful\n", fg=typer.colors.GREEN)
    except typer.Exit:
        # build_files already formatted the error
        typer.secho(
            "\nInitial build failed, continuing in watch mode...\n",
            fg=typer.colors.YELLOW,
        )
    except Exception as e:
        typer.secho(f"Unexpected error: {e}\n", fg=typer.colors.RED, err=True)
        typer.secho(
            "\nInitial build failed, continuing in watch mode...\n",
            fg=typer.colors.YELLOW,
        )

    # Set up file watcher
    event_handler = FileHandler(SOURCE_DIR, BUILD_DIR, pretty)
    observer = Observer()
    observer.schedule(event_handler, str(SOURCE_DIR), recursive=True)
    observer.start()

    typer.secho("Watching for changes... (Press Ctrl+C to stop)", fg=typer.colors.CYAN)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()

    observer.join()
    typer.echo("\nStopped watch mode...")
