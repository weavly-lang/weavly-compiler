import sys
from pathlib import Path

import pytest
import typer

from weavly.parsing.parser import build_all_files


def _project(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.wvl").write_text("@node a\nHi.\n@endnode\n", encoding="utf-8")
    build = tmp_path / "build"
    build.mkdir()
    (build / "old.wvl.json").write_text('{"nodes": []}', encoding="utf-8")
    return src, build


def _entries(tmp_path):
    return sorted(p.name for p in tmp_path.iterdir())


def test_build_replaces_output_and_leaves_no_temp_dirs(tmp_path):
    src, build = _project(tmp_path)

    build_all_files(src, build, pretty=False)

    assert sorted(p.name for p in build.iterdir()) == ["a.wvl.json", "env.json"]
    assert _entries(tmp_path) == ["build", "src"]


def test_leftover_temp_dirs_are_cleaned_up(tmp_path):
    src, build = _project(tmp_path)
    (tmp_path / ".build.tmp" / "stale.json").parent.mkdir()
    (tmp_path / ".build.tmp" / "stale.json").write_text("{}", encoding="utf-8")
    (tmp_path / ".build.old").mkdir()

    build_all_files(src, build, pretty=False)

    assert sorted(p.name for p in build.iterdir()) == ["a.wvl.json", "env.json"]
    assert _entries(tmp_path) == ["build", "src"]


def test_failed_swap_keeps_previous_build(tmp_path, monkeypatch, capsys):
    src, build = _project(tmp_path)
    rename = Path.rename

    def locked_rename(self, target):
        if self == build:
            raise PermissionError(13, "Access is denied", str(self))
        return rename(self, target)

    monkeypatch.setattr(Path, "rename", locked_rename)

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, build, pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "Could not update" in err
    assert "Access is denied" in err
    assert "Traceback" not in err
    assert sorted(p.name for p in build.iterdir()) == ["old.wvl.json"]
    assert _entries(tmp_path) == ["build", "src"]


@pytest.mark.skipif(sys.platform != "win32", reason="Windows file locking")
def test_open_file_in_build_keeps_previous_build(tmp_path):
    src, build = _project(tmp_path)

    with open(build / "old.wvl.json"):
        with pytest.raises(typer.Exit):
            build_all_files(src, build, pretty=False)

    assert sorted(p.name for p in build.iterdir()) == ["old.wvl.json"]
    assert _entries(tmp_path) == ["build", "src"]
