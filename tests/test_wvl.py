import json
from pathlib import Path

import pytest
from lark.exceptions import UnexpectedInput

from weavly.parsing.parser import (
    PARSER_TYPE,
    WVL_GRAMMAR_FILE,
    _build_parser,
    _load_grammar,
    _parse,
)
from weavly.parsing.wvl_transformer import WvlTransformer

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def compile_wvl(source: str) -> dict:
    grammar = _load_grammar(WVL_GRAMMAR_FILE)
    parser = _build_parser(grammar, PARSER_TYPE)
    return _parse(parser, source, WvlTransformer())


wvl_files = sorted(
    p for p in FIXTURES_DIR.rglob("*.wvl") if "invalid" not in p.parts
)

invalid_wvl_files = sorted(FIXTURES_DIR.rglob("invalid/*.wvl"))


@pytest.mark.parametrize(
    "wvl_file",
    wvl_files,
    ids=lambda p: str(p.relative_to(FIXTURES_DIR).with_suffix("")),
)
def test_compile(wvl_file):
    source = wvl_file.read_text(encoding="utf-8")
    expected = json.loads(wvl_file.with_suffix(".json").read_text(encoding="utf-8"))
    assert compile_wvl(source) == expected


@pytest.mark.parametrize(
    "wvl_file",
    invalid_wvl_files,
    ids=lambda p: str(p.relative_to(FIXTURES_DIR).with_suffix("")),
)
def test_compile_error(wvl_file):
    source = wvl_file.read_text(encoding="utf-8")
    with pytest.raises(UnexpectedInput):
        compile_wvl(source)
