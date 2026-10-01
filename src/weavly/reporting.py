from pathlib import Path

import typer


def report_error(
    message: str,
    file: Path | None = None,
    line: int | None = None,
    column: int | None = None,
    details: list[str] | None = None,
) -> None:
    """Print `file:line:column: error: message` to stderr, plus indented details."""
    _report("error", typer.colors.RED, message, file, line, column, details)


def report_warning(message: str, file: Path, line: int, column: int) -> None:
    """Print `file:line:column: warning: message` to stderr."""
    _report("warning", typer.colors.YELLOW, message, file, line, column)


def _report(
    severity: str,
    color: str,
    message: str,
    file: Path | None,
    line: int | None,
    column: int | None,
    details: list[str] | None = None,
) -> None:
    if file is not None:
        location = file.as_posix()
        if line is not None:
            location += f":{line}"
            if column is not None:
                location += f":{column}"
        typer.secho(f"{location}: ", nl=False, bold=True, err=True)
    typer.secho(f"{severity}: ", nl=False, fg=color, bold=True, err=True)
    typer.echo(message, err=True)
    for detail in details or []:
        typer.echo(f"  {detail}", err=True)
