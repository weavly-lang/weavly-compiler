import pytest
import typer
from lark.exceptions import UnexpectedCharacters
from lark.lexer import PatternStr

from weavly.parsing.parser import (
    PARSER_TYPE,
    WVL_GRAMMAR_FILE,
    _build_parser,
    _load_grammar,
    build_all_files,
)
from weavly.parsing.syntax_errors import PATTERN_NAMES, describe_syntax_error


def _build_errors(tmp_path, capsys, source):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.wvl").write_text(source, encoding="utf-8")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    out, err = capsys.readouterr()
    assert out == ""
    return err


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            "@node a\n@options\n@option Go -> a\n@endoptions\n@endnode\n",
            [
                "a.wvl:3:9: error: unexpected 'Go'",
                "  3 | @option Go -> a",
                "    |         ^",
                "  expected one of: '[', a quoted string",
            ],
        ),
        (
            "@node a\n    Hello\n",
            [
                "a.wvl:2:10: error: unexpected end of file",
                "  hint: the @node block opened at line 1 is missing its @endnode",
            ],
        ),
        (
            "@node a\n@if $x\nHi.\n@endnode\n",
            [
                "a.wvl:4:1: error: unexpected '@endnode'",
                "  hint: the @if block opened at line 2 must be closed with @endif first",
            ],
        ),
        (
            "@node a\n@endif\n@endnode\n",
            [
                "a.wvl:2:1: error: unexpected '@endif'",
                "  hint: there is no open @if block for @endif to close",
            ],
        ),
        (
            "@node a\n@option \"x\" -> a\n@endnode\n",
            ["  hint: @option can only be used inside an @options block"],
        ),
        (
            "@node a\n@set $x =\n@endnode\n",
            [
                "a.wvl:2:10: error: unexpected end of line",
                "  expected one of: '$', '(', '-', 'false', 'not', 'true', "
                "a name, a number, a quoted string",
            ],
        ),
        (
            "@node a\n\t@set $x = = 2\n@endnode\n",
            [
                "a.wvl:2:12: error: unexpected '='",
                "  2 | \t@set $x = = 2",
                "    | \t          ^",
            ],
        ),
        (
            "@node a\n@log: player entered the cave\n@endnode\n",
            [
                "a.wvl:2:5: error: unexpected ':'",
                '  hint: command arguments are expressions, like @log "player entered the cave"',
            ],
        ),
        (
            "@node a\n@shake:\n@endnode\n",
            ['  hint: command arguments are expressions, like @shake "text"'],
        ),
        (
            "@node a\nYou have {$gold gold.\n@endnode\n",
            [
                "a.wvl:2:10: error: unclosed '{' in text",
                "  2 | You have {$gold gold.",
                "    |          ^",
                "  hint: close it with '}' or write '\\{' for a literal brace",
            ],
        ),
        (
            "@node a\nYou have {} gold.\n@endnode\n",
            ["a.wvl:2:11: error: unexpected '}'"],
        ),
        (
            '@node a\n@continue "\\"Hi\\" {$x +}"\n@endnode\n',
            ["a.wvl:2:24: error: unexpected '}'"],
        ),
        (
            "@node a\nHi.\n@meta\npool: cave\n@endmeta\n@endnode\n",
            [
                "a.wvl:3:1: error: unexpected '@meta'",
                "  hint: a node can have one @meta block, right after its @node line",
            ],
        ),
        (
            "@node a\n@meta\npool: cave\n",
            ["  hint: the @meta block opened at line 2 is missing its @endmeta"],
        ),
    ],
    ids=[
        "option_without_quotes",
        "missing_endnode",
        "missing_endif",
        "stray_endif",
        "option_outside_options",
        "incomplete_set",
        "tab_indent",
        "command_colon_text",
        "command_colon",
        "unclosed_interpolation",
        "empty_interpolation",
        "interpolation_after_escapes",
        "meta_after_statement",
        "missing_endmeta",
    ],
)
def test_syntax_error_output(tmp_path, capsys, source, expected):
    err = _build_errors(tmp_path, capsys, source)

    for line in expected:
        assert line in err
    assert "_NEWLINE" not in err


def test_every_pattern_terminal_has_a_readable_name():
    parser = _build_parser(_load_grammar(WVL_GRAMMAR_FILE), PARSER_TYPE)
    pattern_terminals = {
        terminal.name
        for terminal in parser.terminals
        if not isinstance(terminal.pattern, PatternStr)
    }

    assert pattern_terminals - PATTERN_NAMES.keys() == set()


def test_unexpected_characters_lists_allowed_terminals():
    error = UnexpectedCharacters("x = ~", 4, 1, 5, allowed={"NUMBER", "STRING"})
    names = {"NUMBER": "a number", "STRING": "a quoted string"}

    message, details = describe_syntax_error(error, "x = ~", names)

    assert message == "unexpected character '~'"
    assert details == [
        "1 | x = ~",
        "  |     ^",
        "expected one of: a number, a quoted string",
    ]
