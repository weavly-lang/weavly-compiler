import pytest
import typer

from weavly.parsing.parser import build_all_files


def test_invalid_escape_is_a_compile_error(tmp_path, capsys):
    src = tmp_path / "src"
    build = tmp_path / "build"
    src.mkdir()
    (src / "bad.wvl").write_text(
        '@env\nok: string = "fine"\npath: string = "C:\\games"\n@endenv\n',
        encoding="utf-8",
    )

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, build, pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "bad.wvl" in err
    assert "Line 3" in err
    assert '"C:\\games"' in err
