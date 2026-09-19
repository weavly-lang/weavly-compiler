import json

import pytest
import typer

from weavly.parsing.parser import build_all_files


def _build(tmp_path, files):
    src = tmp_path / "src"
    src.mkdir()
    for name, content in files.items():
        (src / name).write_bytes(content)
    build_all_files(src, tmp_path / "build", pretty=False)


def test_non_utf8_file_is_reported_with_line(tmp_path, capsys):
    with pytest.raises(typer.Exit) as exc:
        _build(tmp_path, {"a.wvl": b"@node a\nHi.\n\xff bad\n@endnode\n"})

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "Invalid encoding" in err
    assert "a.wvl, Line 3" in err
    assert "Traceback" not in err


def test_utf8_bom_file_builds(tmp_path):
    _build(tmp_path, {"a.wvl": b"\xef\xbb\xbf@node a\nHi.\n@endnode\n"})

    data = json.loads((tmp_path / "build" / "a.wvl.json").read_text(encoding="utf-8"))
    assert data["nodes"][0]["id"] == "a"


def test_errors_in_every_file_are_reported(tmp_path, capsys):
    files = {
        "a.wvl": b"@node a\nHi.\n@endnode\n",
        "b.wvl": b"@node b\n@endif\n@endnode\n",
        "c.wvl": b'@env\npath: string = "C:\\games"\n@endenv\n',
        "d.wvl": b"@node d\n\xff\n@endnode\n",
    }

    with pytest.raises(typer.Exit) as exc:
        _build(tmp_path, files)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "Syntax Error in file:" in err and "b.wvl" in err
    assert "Invalid string in file:" in err and "c.wvl" in err
    assert "Invalid encoding in file:" in err and "d.wvl" in err
    assert not (tmp_path / "build").exists()


def test_file_errors_skip_cross_file_checks(tmp_path, capsys):
    files = {
        "a.wvl": b"@node a\n@goto missing\n@endnode\n",
        "b.wvl": b"@node b\n@endif\n@endnode\n",
    }

    with pytest.raises(typer.Exit):
        _build(tmp_path, files)

    err = capsys.readouterr().err
    assert "b.wvl" in err
    assert "Goto targets" not in err
