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
    if file is not None:
        location = file.as_posix()
        if line is not None:
            location += f":{line}"
            if column is not None:
                location += f":{column}"
        typer.secho(f"{location}: ", nl=False, bold=True, err=True)
    typer.secho("error: ", nl=False, fg=typer.colors.RED, bold=True, err=True)
    typer.echo(message, err=True)
    for detail in details or []:
        typer.echo(f"  {detail}", err=True)
