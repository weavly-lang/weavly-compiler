from weavly.parsing.parser import (
    PARSER_TYPE,
    WENVL_GRAMMAR_FILE,
    WVL_GRAMMAR_FILE,
    _build_parser,
    _load_grammar,
)


def test_wvl_grammar_compiles():
    _build_parser(_load_grammar(WVL_GRAMMAR_FILE), PARSER_TYPE)


def test_wenvl_grammar_compiles():
    _build_parser(_load_grammar(WENVL_GRAMMAR_FILE), PARSER_TYPE)
