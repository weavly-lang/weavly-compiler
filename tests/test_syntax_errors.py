import pytest
import typer
from lark.exceptions import UnexpectedCharacters

from weavly.parsing import build_all_files
from weavly.parsing.parser import create_parser
from weavly.parsing.syntax_errors import describe_syntax_error, terminal_names


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
                "  expected one of: '[', 'node', 'pool', a quoted string",
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
                "a meta value, a name, a number, a quoted string",
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
            "@node a\n@shake(2)\n@endnode\n",
            [
                "a.wvl:2:1: error: unknown keyword '@shake'",
                "  2 | @shake(2)",
                "    | ^",
            ],
        ),
        (
            "@node a\n@if $x\nHi.\n  @endiff\n@endnode\n",
            [
                "a.wvl:4:3: error: unknown keyword '@endiff', did you mean '@endif'?",
                "  4 |   @endiff",
                "    |   ^",
            ],
        ),
        (
            "@node a\n@if $x: @sett $y = 1\n@endif\n@endnode\n",
            ["a.wvl:2:9: error: unknown keyword '@sett', did you mean '@set'?"],
        ),
        (
            "@node a\n@double(2)\n@endnode\n",
            ["a.wvl:2:1: error: unknown keyword '@double', did you mean '@do'?"],
        ),
        (
            "@node start\n@jumpstart\n@endnode\n",
            ["a.wvl:2:1: error: unknown keyword '@jumpstart', did you mean '@jump'?"],
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
        (
            "@env\nvar region: pool\n@endenv\n",
            ["a.wvl:2:17: error: unexpected end of line", "  expected '='"],
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
        "unknown_keyword",
        "unknown_keyword_close_to_one",
        "unknown_keyword_inline",
        "keyword_prefix",
        "keyword_prefix_before_name",
        "unclosed_interpolation",
        "empty_interpolation",
        "interpolation_after_escapes",
        "meta_after_statement",
        "missing_endmeta",
        "name_type_without_default",
    ],
)
def test_syntax_error_output(tmp_path, capsys, source, expected):
    err = _build_errors(tmp_path, capsys, source)

    for line in expected:
        assert line in err
    assert "_NEWLINE" not in err


def test_every_terminal_has_a_readable_name():
    names = terminal_names(create_parser())

    assert [name for name, readable in names.items() if readable == name] == []


def test_unexpected_characters_lists_allowed_terminals():
    error = UnexpectedCharacters("x = ~", 4, 1, 5, allowed={"NUMBER", "STRING"})
    names = {"NUMBER": "a number", "STRING": "a quoted string"}

    message, column, details = describe_syntax_error(error, "x = ~", names)

    assert message == "unexpected character '~'"
    assert column == 5
    assert details == [
        "1 | x = ~",
        "  |     ^",
        "expected one of: a number, a quoted string",
    ]
