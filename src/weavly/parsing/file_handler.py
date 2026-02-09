import time
from pathlib import Path

import typer
from watchdog.events import FileSystemEvent, FileSystemEventHandler

from .parser import WVL_SOURCE_EXTENSION, build_all_files


class FileHandler(FileSystemEventHandler):
    """Handler for file system events in the src directory."""

    def __init__(self, src_dir: Path, build_dir: Path, pretty: bool):
        self.src_dir = src_dir
        self.build_dir = build_dir
        self.pretty = pretty

        # Used to prevent multiple rapid rebuilds
        self.last_build_time = 0
        self.debounce_seconds = 0.5

    def on_modified(self, event: FileSystemEvent):
        if event.is_directory:
            return

        if not event.src_path.endswith(WVL_SOURCE_EXTENSION):
            return

        current_time = time.time()
        if current_time - self.last_build_time < self.debounce_seconds:
            return

        self.last_build_time = current_time

        typer.echo(f"\nChange detected in file: {Path(event.src_path).name}")
        try:
            build_all_files(self.src_dir, self.build_dir, self.pretty)
            typer.secho("Rebuild successful", fg=typer.colors.GREEN)
        except typer.Exit:
            # build_files will print its error
            pass
        except Exception as e:
            typer.secho(f"Unexpected error: {e}", fg=typer.colors.RED, err=True)
