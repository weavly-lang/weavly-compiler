from pathlib import Path

import pytest
import typer
from lark.exceptions import UnexpectedCharacters

from weavly.parsing.parser import _report_parse_error, build_all_files


def test_unexpected_characters_lists_allowed_terminals(capsys):
    error = UnexpectedCharacters("x = ~", 4, 1, 5, allowed={"NUMBER", "STRING"})

    _report_parse_error(error, Path("story.wvl"))

    out, err = capsys.readouterr()
    assert out == ""
    assert "story.wvl:1:5: error: syntax error, unexpected character '~'" in err
    assert "NUMBER" in err
    assert "STRING" in err


def test_syntax_error_output_goes_to_stderr_only(tmp_path, capsys):
    src = tmp_path / "src"
    src.mkdir()
    (src / "bad.wvl").write_text("@node start\n@endif\n@endnode\n", encoding="utf-8")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    out, err = capsys.readouterr()
    assert out == ""
    assert "bad.wvl" in err
    assert "expected one of:" in err
