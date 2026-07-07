from weavly.parsing.parser import (
    PARSER_TYPE,
    WVL_GRAMMAR_FILE,
    _build_parser,
    _load_grammar,
)


def test_wvl_grammar_compiles():
    _build_parser(_load_grammar(WVL_GRAMMAR_FILE), PARSER_TYPE)
