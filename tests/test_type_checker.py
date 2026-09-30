import json

import pytest
import typer

from weavly.parsing import build_all_files

ENV = (
    "@env\n"
    "var score: number = 0\n"
    'var name: string = "Hero"\n'
    "var has_key: flag = false\n"
    "extern var reputation: number\n"
    "pool cave\n"
    "pool hall\n"
    "slot treasure\n"
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
        ("Costs {$score + $scroe}.", "2:17"),
        ('@continue "\\"Hi\\" {$scroe}"', "2:20"),
    ],
    ids=["expression", "set", "increase", "decrease", "setflag", "clearflag",
         "character_name", "narration_text", "named_character_text", "character_text",
         "option_text", "hint_text", "continue_text", "text_expression",
         "text_after_escapes"],
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
        ("Costs {$name * 2}.", "2:8: error: '*' needs a number, got a string"),
        (
            '@options\n@option "Is {$score == \\"x\\"}" -> start\n@endoptions',
            "3:14: error: '==' needs both sides of the same type, got a number and a string",
        ),
    ],
    ids=["set", "set_function", "add", "mul", "neg", "div_node_function", "and", "or",
         "not", "compare_eq", "compare_lt", "function_argument", "function_arguments",
         "increase", "decrease", "setflag", "clearflag", "character_name", "text",
         "option_text"],
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
    _write(src / "z" / "b.wvl", "@env\nextern var gold: number\n@endenv\n")

    build_all_files(src, tmp_path / "build", pretty=False)


def test_extern_declarations_are_written_to_env_json(tmp_path):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)

    build_all_files(src, tmp_path / "build", pretty=False)

    env = json.loads((tmp_path / "build" / "env.json").read_text(encoding="utf-8"))
    assert env["declarations"][-1] == {"type": "number", "name": "reputation", "extern": True}


def test_extern_and_regular_declaration_with_same_name_is_an_error(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@env\nvar gold: number = 0\n@endenv\n")
    _write(src / "b.wvl", "@env\nextern var gold: number\n@endenv\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    assert "b.wvl:2:12: error: duplicate variable 'gold', first declared at" in (
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


def test_functions_in_text_are_checked(tmp_path, capsys):
    errors = _build_errors(
        tmp_path, capsys, 'Hi {maxx(1, 2)} {clamp(1, 2)}\n@continue "{visited(gone)}"'
    )

    assert errors == [
        "2:5: error: unknown function 'maxx', did you mean 'max'?",
        "2:18: error: clamp() takes 3 arguments, got 2",
        "3:21: error: visited target 'gone' matches no node",
    ]


@pytest.mark.parametrize(
    "body, expected",
    [
        (
            "@meta\npools: cave\n@endmeta",
            "3:1: error: unknown meta key 'pools', did you mean 'pool'?",
        ),
        ("@meta\npool: cave\npool: hall\n@endmeta", "4:1: error: duplicate meta key 'pool'"),
        ("@meta\nwhen: $score\n@endmeta", "3:7: error: when needs a flag, got a number"),
        ("@meta\nweight: $has_key\n@endmeta", "3:9: error: weight needs a number, got a flag"),
        ("@meta\npriority: $name\n@endmeta", "3:11: error: priority needs a number, got a string"),
        (
            "@meta\npriority: cave\n@endmeta",
            "3:11: error: priority needs a number, got a pool",
        ),
        ("@meta\nonce: $has_key\n@endmeta", "3:7: error: once needs true or false"),
        ("@meta\nwhen: true, false\n@endmeta", "3:13: error: when takes a single value, got 2"),
        ("@meta\npool: cavee\n@endmeta", "3:7: error: pool 'cavee' isn't declared"),
        ("@meta\nslot: tresure\n@endmeta", "3:7: error: slot 'tresure' isn't declared"),
        ("@meta\npool: cave, treasure\n@endmeta", "3:13: error: 'treasure' is a slot, not a pool"),
        ("@meta\npool: score\n@endmeta", "3:7: error: 'score' is a variable, not a pool"),
        ("@meta\npool: $score\n@endmeta", "3:7: error: pool takes pool names, not expressions"),
        ("@meta\nwhen: $gold > 1\n@endmeta", "3:7: error: variable 'gold' isn't declared"),
        (
            "@meta\nwhen: visited(gone)\n@endmeta",
            "3:15: error: visited target 'gone' matches no node",
        ),
        ("@if $cave\n    Hi.\n@endif", "2:5: error: 'cave' is a pool, not a variable"),
        ("@set $cave = 1", "2:6: error: 'cave' is a pool, not a variable"),
        ("Hi {$treasure}.", "2:5: error: 'treasure' is a slot, not a variable"),
    ],
    ids=["unknown_key", "duplicate_key", "when", "weight", "priority", "priority_name",
         "once", "several_values", "undeclared_pool", "undeclared_slot", "slot_as_pool",
         "variable_as_pool", "expression_as_pool", "undeclared_variable", "visited_target",
         "pool_in_condition", "pool_in_set", "slot_in_text"],
)
def test_meta_errors(tmp_path, capsys, body, expected):
    assert _build_errors(tmp_path, capsys, body) == [expected]


def test_meta_block_builds(tmp_path):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)
    _write(
        src / "a.wvl",
        "@node start\n"
        "@meta\n"
        "pool: cave, hall\n"
        "slot: treasure\n"
        "when: $score > 5 and not $has_key\n"
        "priority: clamp($reputation, 0, 10)\n"
        "weight: 1 + visit_count(start)\n"
        "once: true\n"
        "@endmeta\n"
        "Hi.\n"
        "@endnode\n",
    )

    build_all_files(src, tmp_path / "build", pretty=False)

    data = json.loads((tmp_path / "build" / "a.wvl.json").read_text(encoding="utf-8"))
    assert list(data["nodes"][0]["meta"]) == ["pool", "slot", "when", "priority", "weight"]


@pytest.mark.parametrize(
    "body, expected",
    [
        ("@draw cavee", "2:7: error: pool 'cavee' isn't declared"),
        ("@draw cave, treasure", "2:13: error: 'treasure' is a slot, not a pool"),
        ("@draw score", "2:7: error: 'score' is a variable, not a pool"),
        (
            '@options\n@option "Go": @draw nowhere\n@endoptions',
            "3:21: error: pool 'nowhere' isn't declared",
        ),
    ],
    ids=["undeclared", "slot", "variable", "inline"],
)
def test_draw_errors(tmp_path, capsys, body, expected):
    assert _build_errors(tmp_path, capsys, body) == [expected]


def test_draw_from_pools_without_members_builds(tmp_path):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)
    _write(src / "a.wvl", "@node start\n@draw cave, hall, cave\nNothing here.\n@endnode\n")

    build_all_files(src, tmp_path / "build", pretty=False)

    data = json.loads((tmp_path / "build" / "a.wvl.json").read_text(encoding="utf-8"))
    assert data["nodes"][0]["body"][0] == {
        "type": "draw",
        "line": 2,
        "pools": ["cave", "hall", "cave"],
    }


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


NAME_ENV = ENV + "@env\nvar region: pool = cave\nvar quest: node = start\n@endenv\n"


@pytest.mark.parametrize(
    "body, expected",
    [
        ("@set $region = treasure", "2:16: error: @set $region needs a pool, got a slot"),
        ("@set $region = 1", "2:16: error: @set $region needs a pool, got a number"),
        ("@set $quest = cave", "2:15: error: @set $quest needs a node, got a pool"),
        (
            "@if $region == treasure\n    Hi.\n@endif",
            "2:5: error: '==' needs both sides of the same type, got a pool and a slot",
        ),
        ("@if $region < hall\n    Hi.\n@endif", "2:5: error: '<' can't compare pools"),
        ("@set $score = cave + 1", "2:15: error: '+' needs a number, got a pool"),
        ("@if cave\n    Hi.\n@endif", "2:5: error: condition needs a flag, got a pool"),
        ("@spawn wolf", "2:8: error: 'wolf' isn't a node, pool or slot"),
        ("You have {score} gold.", "2:11: error: 'score' is a variable, write $score"),
        (
            "@increase $region",
            "2:11: error: @increase needs a number variable, 'region' is a pool",
        ),
        (
            "@if visited(start, start)\n    Hi.\n@endif",
            "2:5: error: visited() takes a node id, or none for the current node",
        ),
    ],
    ids=["set_slot", "set_number", "set_pool_as_node", "compare_types", "order",
         "arithmetic", "condition", "undeclared", "variable_without_marker", "increase",
         "node_function_two_names"],
)
def test_name_errors(tmp_path, capsys, body, expected):
    src = tmp_path / "src"
    _write(src / "globals.wvl", NAME_ENV)
    _write(src / "a.wvl", f"@node start\n{body}\n@endnode\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    errors = [line.split("a.wvl:", 1)[1] for line in capsys.readouterr().err.splitlines()]
    assert errors == [expected]


@pytest.mark.parametrize(
    "declaration, expected",
    [
        ("var region: pool = treasure", "2:20: error: 'treasure' is a slot, not a pool"),
        ("var region: pool = cavee", "2:20: error: pool 'cavee' isn't declared"),
        ("var region: pool = score", "2:20: error: 'score' is a variable, not a pool"),
        ("var quest: node = gone", "2:19: error: 'gone' matches no node"),
    ],
    ids=["slot_as_pool", "undeclared_pool", "variable_as_pool", "missing_node"],
)
def test_name_variable_defaults_are_checked(tmp_path, capsys, declaration, expected):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)
    _write(src / "a.wvl", f"@env\n{declaration}\n@endenv\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    errors = [line.split("a.wvl:", 1)[1] for line in capsys.readouterr().err.splitlines()]
    assert errors == [expected]


def test_name_variables_build(tmp_path):
    src = tmp_path / "src"
    _write(
        src / "a.wvl",
        "@env\n"
        "pool cave\n"
        "slot treasure\n"
        "var region: pool = cave\n"
        "var quest: node = cave\n"
        "var partner: slot = treasure\n"
        "extern var home: pool\n"
        "@endenv\n\n"
        "@node cave\n"
        "@if $region == cave and cave == $quest and $home != $region and visited(cave)\n"
        "    @set $region = cave\n"
        "    @set $quest = cave\n"
        "@endif\n"
        "@unlock cave, $partner\n"
        "You reach {cave}.\n"
        "@endnode\n",
    )

    build_all_files(src, tmp_path / "build", pretty=False)

    env = json.loads((tmp_path / "build" / "env.json").read_text(encoding="utf-8"))
    assert env == {
        "declarations": [
            {"type": "pool", "name": "region", "value": "cave"},
            {"type": "node", "name": "quest", "value": "cave"},
            {"type": "slot", "name": "partner", "value": "treasure"},
            {"type": "pool", "name": "home", "extern": True},
        ],
        "pools": ["cave"],
        "slots": ["treasure"],
        "meta_keys": [],
    }


META_ENV = ENV + "@env\nmeta cost: number = 1\nmeta art: string\nmeta home: pool = cave\n@endenv\n"


@pytest.mark.parametrize(
    "body, expected",
    [
        ('@meta\ncost: "x"\n@endmeta', "3:7: error: cost needs a number, got a string"),
        ("@meta\ncots: 1\n@endmeta", "3:1: error: unknown meta key 'cots', did you mean 'cost'?"),
        ("@meta\nhome: treasure\n@endmeta", "3:7: error: home needs a pool, got a slot"),
        ("@meta\nhome: cave, hall\n@endmeta", "3:13: error: home takes a single value, got 2"),
        (
            "@set $score = meta(cots)",
            "2:20: error: unknown meta key 'cots', did you mean 'cost'?",
        ),
        ("@set $score = meta(art)", "2:15: error: @set $score needs a number, got a string"),
        ("@if meta(pool)\n    Hi.\n@endif", "2:10: error: meta() can't read pool"),
        ("@set $score = meta(gone, cost)", "2:20: error: meta target 'gone' matches no node"),
        (
            "@set $score = meta($score)",
            "2:15: error: meta() takes a meta key, or a node id and a meta key",
        ),
        ("@set $score = $cost", "2:15: error: 'cost' is a meta key, not a variable"),
        ("@draw cost", "2:7: error: 'cost' is a meta key, not a pool"),
        ("@set $score = cost", "2:15: error: 'cost' is a meta key, write meta(cost)"),
    ],
    ids=["wrong_type", "unknown_key", "name_type", "several_values", "unknown_read",
         "read_type", "unreadable", "missing_node", "not_a_name", "as_variable",
         "as_pool", "without_meta"],
)
def test_meta_key_errors(tmp_path, capsys, body, expected):
    src = tmp_path / "src"
    _write(src / "globals.wvl", META_ENV)
    _write(src / "a.wvl", f"@node start\n{body}\n@endnode\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    errors = [line.split("a.wvl:", 1)[1] for line in capsys.readouterr().err.splitlines()]
    assert errors == [expected]


@pytest.mark.parametrize(
    "declaration, expected",
    [
        ("meta pool: number", "2:6: error: 'pool' is a built-in meta key"),
        ("meta home: pool = treasure", "2:19: error: 'treasure' is a slot, not a pool"),
        ("meta score: number", "2:6: error: duplicate meta key 'score', first declared at"),
    ],
    ids=["built_in", "name_default", "duplicate"],
)
def test_meta_declaration_errors(tmp_path, capsys, declaration, expected):
    src = tmp_path / "src"
    _write(src / "globals.wvl", ENV)
    _write(src / "z.wvl", f"@env\n{declaration}\n@endenv\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    errors = [line.split("z.wvl:", 1)[1] for line in capsys.readouterr().err.splitlines()]
    assert len(errors) == 1
    assert errors[0].startswith(expected)


@pytest.mark.parametrize(
    "nodes, expected",
    [
        (
            "@node a\n@meta\ncost: meta(cost) + 1\n@endmeta\n@endnode\n",
            ["3:1: error: meta key 'cost' reads itself: a.cost -> a.cost"],
        ),
        (
            "@node a\n@meta\ncost: meta(weight)\nweight: meta(cost)\n@endmeta\n@endnode\n",
            ["3:1: error: meta key 'cost' reads itself: a.cost -> a.weight -> a.cost"],
        ),
        (
            "@node a\n@meta\ncost: meta(b, cost)\n@endmeta\n@endnode\n"
            "@node b\n@meta\ncost: 1 + meta(a, cost)\n@endmeta\n@endnode\n",
            ["3:1: error: meta key 'cost' reads itself: a.cost -> b.cost -> a.cost"],
        ),
    ],
    ids=["self", "two_keys", "two_nodes"],
)
def test_meta_values_that_read_themselves_are_errors(tmp_path, capsys, nodes, expected):
    src = tmp_path / "src"
    _write(src / "globals.wvl", META_ENV)
    _write(src / "a.wvl", nodes)

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    errors = [line.split("a.wvl:", 1)[1] for line in capsys.readouterr().err.splitlines()]
    assert errors == expected


def test_meta_keys_build(tmp_path):
    src = tmp_path / "src"
    _write(src / "globals.wvl", META_ENV)
    _write(
        src / "a.wvl",
        "@node start\n"
        "@meta\n"
        "pool: cave\n"
        "cost: 1 + $score\n"
        'art: "fire_{$name}"\n'
        "home: hall\n"
        "weight: meta(cost) + meta(other, cost)\n"
        "when: meta(start, home) == hall and meta(priority) > 0\n"
        "@endmeta\n"
        "Costs {meta(cost)}.\n"
        "@endnode\n"
        "@node other\n"
        "@meta\n"
        "cost: meta(start, priority)\n"
        "@endmeta\n"
        "@endnode\n",
    )

    build_all_files(src, tmp_path / "build", pretty=False)

    env = json.loads((tmp_path / "build" / "env.json").read_text(encoding="utf-8"))
    assert env["meta_keys"] == [
        {"type": "number", "name": "cost", "value": 1.0},
        {"type": "string", "name": "art", "value": ""},
        {"type": "pool", "name": "home", "value": "cave"},
    ]
