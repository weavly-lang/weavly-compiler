import json

import pytest
import typer

from weavly.parsing.parser import build_all_files

ENV = (
    "@env\n"
    "score: number = 0\n"
    'name: string = "Hero"\n'
    "has_key: flag = false\n"
    "extern reputation: number\n"
    "@endenv\n"
)


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_errors(tmp_path, capsys, body):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)
    _write(src / "a.wvl", f"@node start\n{body}\n@endnode\n")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    return [line.split("a.wvl:", 1)[1] for line in capsys.readouterr().err.splitlines()]


@pytest.mark.parametrize(
    "body, expected",
    [
        ("@if $scroe > 1\n    Hi.\n@endif", "2:5"),
        ("@set $scroe = 1", "2:6"),
        ("@increase $scroe", "2:11"),
        ("@decrease $scroe 2", "2:11"),
        ("@setflag $scroe", "2:10"),
        ("@clearflag $scroe", "2:12"),
        ("$scroe: Hi.", "2:1"),
        ("Hello {$scroe}.", "2:8"),
        (">Guide: Hi {$scroe}.", "2:13"),
        ("$name: Hi {$scroe}.", "2:12"),
        ('@options\n@option "Pay {$scroe}" -> start\n@endoptions', "3:15"),
        ('@options\n@hint "Need {$scroe}"\n@endoptions', "3:14"),
        ('@continue "Onward, {$scroe}"', "2:21"),
    ],
    ids=["expression", "set", "increase", "decrease", "setflag", "clearflag",
         "character_name", "narration_text", "named_character_text", "character_text",
         "option_text", "hint_text", "continue_text"],
)
def test_undeclared_variables_are_errors(tmp_path, capsys, body, expected):
    errors = _build_errors(tmp_path, capsys, body)

    assert errors == [f"{expected}: error: variable 'scroe' isn't declared"]


@pytest.mark.parametrize(
    "body, expected",
    [
        ('@set $score = "high"', "2:15: error: @set $score needs a number, got a string"),
        (
            "@set $has_key = visit_count(start)",
            "2:17: error: @set $has_key needs a flag, got a number",
        ),
        ("@set $score = $name + 1", "2:15: error: '+' needs a number, got a string"),
        ("@set $score = 2 * $has_key", "2:19: error: '*' needs a number, got a flag"),
        ("@set $score = -$has_key", "2:16: error: '-' needs a number, got a flag"),
        ("@set $score = visited(start) / 2", "2:15: error: '/' needs a number, got a flag"),
        ("@set $has_key = $score and true", "2:17: error: 'and' needs a flag, got a number"),
        ("@set $has_key = true or $name", "2:25: error: 'or' needs a flag, got a string"),
        ("@set $has_key = not $name", "2:21: error: 'not' needs a flag, got a string"),
        (
            '@set $has_key = $score == "x"',
            "2:17: error: '==' needs both sides of the same type, got a number and a string",
        ),
        (
            "@set $has_key = $has_key < 1",
            "2:17: error: '<' needs both sides of the same type, got a flag and a number",
        ),
        ("@set $score = round($name)", "2:21: error: round() needs a number, got a string"),
        ("@set $score = min(1, $has_key)", "2:22: error: min() needs a number, got a flag"),
        ("@increase $name", "2:11: error: @increase needs a number variable, 'name' is a string"),
        (
            "@decrease $has_key",
            "2:11: error: @decrease needs a number variable, 'has_key' is a flag",
        ),
        ("@setflag $score", "2:10: error: @setflag needs a flag variable, 'score' is a number"),
        ("@clearflag $name", "2:12: error: @clearflag needs a flag variable, 'name' is a string"),
        (
            "$score: Hi.",
            "2:1: error: character name needs a string variable, 'score' is a number",
        ),
    ],
    ids=["set", "set_function", "add", "mul", "neg", "div_node_function", "and", "or",
         "not", "compare_eq", "compare_lt", "function_argument", "function_arguments",
         "increase", "decrease", "setflag", "clearflag", "character_name"],
)
def test_type_errors(tmp_path, capsys, body, expected):
    assert _build_errors(tmp_path, capsys, body) == [expected]


@pytest.mark.parametrize(
    "body, expected",
    [
        ("@if $score\n    Hi.\n@endif", "2:5"),
        ("@if true\n    Hi.\n@elif $reputation\n    Ho.\n@endif", "4:7"),
        ("@match\n@when $score: Hi.\n@endmatch", "3:7"),
        ('@options\n@option [$score] "A" -> start\n@endoptions', "3:10"),
        ('@options\n@hint [$score] "A"\n@endoptions', "3:8"),
        ("@random\n@case [$score] 1: Hi.\n@endrandom", "3:8"),
        ("@if visit_count(start)\n    Hi.\n@endif", "2:5"),
    ],
    ids=["if", "elif", "when", "option", "hint", "case", "function"],
)
def test_conditions_must_be_flags(tmp_path, capsys, body, expected):
    errors = _build_errors(tmp_path, capsys, body)

    assert len(errors) == 1
    assert errors[0].startswith(f"{expected}: error: condition needs a flag, got a ")


def test_random_weight_must_be_a_number(tmp_path, capsys):
    errors = _build_errors(tmp_path, capsys, "@random\n@case $has_key: Hi.\n@endrandom")

    assert errors == ["3:7: error: random weight needs a number, got a flag"]


def test_undeclared_variable_does_not_cascade(tmp_path, capsys):
    errors = _build_errors(tmp_path, capsys, "@set $has_key = not ($missing + 1 > 2)")

    assert errors == ["2:22: error: variable 'missing' isn't declared"]


def test_every_type_error_is_reported(tmp_path, capsys):
    errors = _build_errors(
        tmp_path, capsys, '@set $score = "a"\n@if $name\n    Hi {$gold}.\n@endif'
    )

    assert errors == [
        "2:15: error: @set $score needs a number, got a string",
        "3:5: error: condition needs a flag, got a string",
        "4:9: error: variable 'gold' isn't declared",
    ]


def test_well_typed_script_builds(tmp_path):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)
    _write(
        src / "a.wvl",
        "@node start\n"
        "$name: Hello {$name}, you have {$score} points and {$reputation} reputation.\n"
        "@set $score = clamp($score + $reputation * 2, 0, 100)\n"
        "@increase $reputation\n"
        "@setflag $has_key\n"
        '@if visited(start) and $name == "Hero" and $has_key != false\n'
        "    @set $has_key = $score >= visit_count(start) or not $has_key\n"
        "@endif\n"
        "@random\n"
        "@case [$score > 1] $score: Hi.\n"
        "@endrandom\n"
        "@endnode\n",
    )

    build_all_files(src, tmp_path / "build", pretty=False)


def test_variables_declared_in_other_files_are_known(tmp_path):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@node start\n@increase $gold\n@endnode\n")
    _write(src / "z" / "b.wvl", "@env\nextern gold: number\n@endenv\n")

    build_all_files(src, tmp_path / "build", pretty=False)


def test_extern_declarations_are_written_to_env_json(tmp_path):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)

    build_all_files(src, tmp_path / "build", pretty=False)

    env = json.loads((tmp_path / "build" / "env.json").read_text(encoding="utf-8"))
    assert env["declarations"][-1] == {"type": "number", "name": "reputation", "extern": True}


def test_extern_and_regular_declaration_with_same_name_is_an_error(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@env\ngold: number = 0\n@endenv\n")
    _write(src / "b.wvl", "@env\nextern gold: number\n@endenv\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    assert "b.wvl:2:8: error: duplicate variable 'gold', first declared at" in (
        capsys.readouterr().err
    )


def test_command_arguments_are_checked(tmp_path, capsys):
    errors = _build_errors(
        tmp_path,
        capsys,
        '@play_sound "door", $volume\n@shake $name + 1, clamp(1, 2), visited(gone)',
    )

    assert errors == [
        "2:21: error: variable 'volume' isn't declared",
        "3:8: error: '+' needs a number, got a string",
        "3:19: error: clamp() takes 3 arguments, got 2",
        "3:40: error: visited target 'gone' matches no node",
    ]


def test_command_arguments_of_any_type_build(tmp_path):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)
    _write(
        src / "a.wvl",
        '@node start\n@log "{$name}", $name, $score * 2, $has_key, visited(start)\n@endnode\n',
    )

    build_all_files(src, tmp_path / "build", pretty=False)

    data = json.loads((tmp_path / "build" / "a.wvl.json").read_text(encoding="utf-8"))
    assert data["nodes"][0]["body"][0]["args"] == [
        "{$name}",
        {"variable": "name"},
        {"op": "*", "left": {"variable": "score"}, "right": 2.0},
        {"variable": "has_key"},
        {"call": "visited", "node": "start"},
    ]
