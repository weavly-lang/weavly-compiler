from pathlib import Path

import pytest

from weavly.reporting import report_error


@pytest.mark.parametrize(
    "kwargs, expected",
    [
        ({}, "error: boom\n"),
        ({"file": Path("src/a.wvl")}, "src/a.wvl: error: boom\n"),
        ({"file": Path("src/a.wvl"), "line": 3}, "src/a.wvl:3: error: boom\n"),
        (
            {"file": Path("src/a.wvl"), "line": 3, "column": 7},
            "src/a.wvl:3:7: error: boom\n",
        ),
        ({"details": ["one", "two"]}, "error: boom\n  one\n  two\n"),
    ],
)
def test_report_error_format(capsys, kwargs, expected):
    report_error("boom", **kwargs)

    out, err = capsys.readouterr()
    assert out == ""
    assert err == expected
