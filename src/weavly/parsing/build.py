import json
import shutil
from contextlib import suppress
from pathlib import Path

import typer
from lark import Tree
from lark.exceptions import UnexpectedInput, VisitError

from ..reporting import report_error
from .checks import ProjectChecks
from .parser import create_parser, parse
from .syntax_errors import describe_syntax_error, terminal_names
from .wvl_transformer import InvalidStringError, WvlTransformer

ENCODING = "utf-8"
SOURCE_ENCODING = "utf-8-sig"

WVL_SOURCE_EXTENSION = ".wvl"
WVL_BUILD_EXTENSION = ".wvl.json"
ENV_BUILD_FILE = "env.json"

# declaration type -> env.json list of names.
_NAME_LISTS = {"pool": "pools", "slot": "slots"}


def build_all_files(src_dir: Path, build_dir: Path, pretty: bool) -> int:
    if not src_dir.is_dir():
        report_error(
            f"no '{src_dir.as_posix()}' directory found. Run 'weavly init' to create "
            "a project or run the build from the project root."
        )
        raise typer.Exit(code=1)

    names = terminal_names(create_parser())
    transformer = WvlTransformer()
    checks = ProjectChecks()
    declarations: list[dict] = []
    outputs: list[tuple[Path, dict]] = []
    failed = False

    for file in sorted(src_dir.rglob(f"*{WVL_SOURCE_EXTENSION}")):
        if not file.is_file():
            continue
        compiled = _compile_file(file, transformer, names)
        if compiled is None:
            failed = True
            continue

        tree, data = compiled
        checks.add_file(file, tree)
        declarations.extend(data.get("declarations", []))
        relative_path = file.relative_to(src_dir)
        outputs.append(
            (
                relative_path.with_suffix(WVL_BUILD_EXTENSION),
                {"source": relative_path.as_posix(), "nodes": data["nodes"]},
            )
        )

    if failed:
        raise typer.Exit(code=1)

    errors = checks.finish(declarations)
    if errors:
        for (file, line, column), message in sorted(errors):
            report_error(message, file, line, column)
        raise typer.Exit(code=1)

    file_count = len(outputs)
    outputs.append((Path(ENV_BUILD_FILE), _env(declarations)))
    _replace_build_dir(build_dir, outputs, pretty)
    return file_count


def _compile_file(
    file: Path, transformer: WvlTransformer, names: dict[str, str]
) -> tuple[Tree, dict] | None:
    """Parse and transform `file`, or report why it can't be and return None."""
    try:
        text = file.read_text(encoding=SOURCE_ENCODING)
    except UnicodeDecodeError as e:
        line = e.object[: e.start].count(b"\n") + 1
        report_error("invalid encoding, files must be saved as UTF-8", file, line)
        return None

    try:
        tree = parse(text)
        return tree, transformer.transform(tree)
    except UnexpectedInput as e:
        message, details = describe_syntax_error(e, text, names)
        report_error(message, file, e.line, e.column, details)
    except InvalidStringError as e:
        _report_string_error(e, file)
    except VisitError as e:
        if not isinstance(e.orig_exc, InvalidStringError):
            raise
        _report_string_error(e.orig_exc, file)
    return None


def _report_string_error(error: InvalidStringError, file: Path) -> None:
    token = error.token
    report_error(
        f"invalid string {token.value}: {error.reason}", file, token.line, token.column
    )


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
        if old_dir.exists() and not build_dir.exists():
            with suppress(OSError):
                old_dir.rename(build_dir)
        report_error(
            f"could not update '{build_dir.as_posix()}': {e.strerror or e}. "
            "Close any program using its files and build again."
        )
        raise typer.Exit(code=1)
    shutil.rmtree(old_dir, ignore_errors=True)


def _write_json(data: dict, out_file: Path, pretty: bool) -> None:
    out_file.parent.mkdir(parents=True, exist_ok=True)
    if pretty:
        out_file.write_text(json.dumps(data, indent=2), encoding=ENCODING)
    else:
        out_file.write_text(json.dumps(data, separators=(",", ":")), encoding=ENCODING)
