import pytest
import typer

from weavly.parsing import build_all_files


def test_invalid_escape_is_a_compile_error(tmp_path, capsys):
    src = tmp_path / "src"
    build = tmp_path / "build"
    src.mkdir()
    (src / "bad.wvl").write_text(
        '@env\nvar ok: string = "fine"\nvar path: string = "C:\\games"\n@endenv\n',
        encoding="utf-8",
    )

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, build, pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "bad.wvl" in err
    assert "bad.wvl:3:20: error: invalid string" in err
    assert '"C:\\games"' in err


def test_invalid_escape_in_text_is_a_compile_error(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "bad.wvl").write_text(
        '@node a\n@continue "Open C:\\games"\n@endnode\n', encoding="utf-8"
    )

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    assert 'bad.wvl:2:11: error: invalid string "Open C:\\games"' in capsys.readouterr().err
