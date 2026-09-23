import json

import pytest
import typer

from weavly.parsing.parser import build_all_files


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_declarations_merge_into_single_env_json(tmp_path):
    src = tmp_path / "src"
    build = tmp_path / "build"

    _write(
        src / "globals.wvl",
        "@env\nhp: number(0, 100) = 50\ngold: number = 0\n@endenv\n",
    )
    _write(
        src / "scenes" / "witch.wvl",
        "@env\nbrave: flag = true\n@endenv\n\n@node witch\nThe witch cackles.\n@endnode\n",
    )

    build_all_files(src, build, pretty=False)

    env = json.loads((build / "env.json").read_text(encoding="utf-8"))
    names = [d["name"] for d in env["declarations"]]
    assert names == ["hp", "gold", "brave"]

    # Per-file artifacts carry nodes only, never declarations.
    globals_json = json.loads(
        (build / "globals.wvl.json").read_text(encoding="utf-8")
    )
    assert globals_json == {"source": "globals.wvl", "nodes": []}

    witch_json = json.loads(
        (build / "scenes" / "witch.wvl.json").read_text(encoding="utf-8")
    )
    assert "declarations" not in witch_json
    assert witch_json["source"] == "scenes/witch.wvl"
    assert witch_json["nodes"][0]["id"] == "witch"
    assert witch_json["nodes"][0]["line"] == 5


def test_duplicate_declaration_across_files_is_an_error(tmp_path, capsys):
    src = tmp_path / "src"
    build = tmp_path / "build"

    _write(src / "a.wvl", "@env\nhp: number = 50\n@endenv\n")
    _write(src / "b.wvl", "@env\nhp: number = 10\n@endenv\n")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, build, pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "hp" in err
    # Both locations are named.
    assert "a.wvl" in err
    assert "b.wvl" in err


def test_missing_src_dir_is_an_error_and_keeps_build(tmp_path, capsys):
    build = tmp_path / "build"
    _write(build / "old.wvl.json", '{"nodes": []}')

    with pytest.raises(typer.Exit) as exc:
        build_all_files(tmp_path / "src", build, pretty=False)

    assert exc.value.exit_code == 1
    assert "weavly init" in capsys.readouterr().err
    assert (build / "old.wvl.json").exists()


def test_missing_src_dir_does_not_create_build(tmp_path):
    with pytest.raises(typer.Exit):
        build_all_files(tmp_path / "src", tmp_path / "build", pretty=False)

    assert not (tmp_path / "build").exists()


@pytest.mark.parametrize(
    "bad_source",
    [
        "@node b\n@endif\n@endnode\n",
        '@env\npath: string = "C:\\games"\n@endenv\n',
        "@env\nhp: number = 10\n@endenv\n",
    ],
    ids=["parse_error", "invalid_string", "duplicate_declaration"],
)
def test_failed_build_keeps_previous_build(tmp_path, bad_source):
    src = tmp_path / "src"
    build = tmp_path / "build"
    _write(src / "a.wvl", "@env\nhp: number = 50\n@endenv\n\n@node a\nHi.\n@endnode\n")
    _write(build / "old.wvl.json", '{"nodes": []}')
    _write(src / "b.wvl", bad_source)

    with pytest.raises(typer.Exit):
        build_all_files(src, build, pretty=False)

    assert sorted(p.name for p in build.iterdir()) == ["old.wvl.json"]


def test_duplicate_node_id_across_files_is_an_error(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@node intro\nHi.\n@endnode\n")
    _write(src / "b.wvl", "\n@node intro\nHello.\n@endnode\n")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "b.wvl:2:7: error: duplicate node id 'intro', first declared at" in err
    assert "a.wvl:1" in err


def test_unresolved_goto_targets_are_errors(tmp_path, capsys):
    src = tmp_path / "src"
    _write(
        src / "a.wvl",
        "@node start\n@goto missing\n@continue \"Go\" -> nowhere\n@goto finale\n@endnode\n",
    )
    _write(src / "b.wvl", "@node finale\nThe end.\n@endnode\n")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "a.wvl:2:7: error: goto target 'missing' matches no node" in err
    assert "a.wvl:3:19: error: goto target 'nowhere' matches no node" in err
    assert "finale" not in err


def test_unresolved_visit_targets_are_errors(tmp_path, capsys):
    src = tmp_path / "src"
    _write(
        src / "a.wvl",
        "@node start\n"
        "@if visited(shpo) or visit_count(inn) > 1\n    Hi.\n@endif\n"
        "@set $count = visit_count(gone) + visit_count(shop)\n"
        "@endnode\n",
    )
    _write(src / "b.wvl", "@node shop\nThe shop.\n@endnode\n")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "a.wvl:2:13: error: visited target 'shpo' matches no node" in err
    assert "a.wvl:2:34: error: visit_count target 'inn' matches no node" in err
    assert "a.wvl:5:27: error: visit_count target 'gone' matches no node" in err
    assert "'shop'" not in err


def test_unknown_function_is_an_error(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@node start\n@if visted(start)\n    Hi.\n@endif\n@endnode\n")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert "a.wvl:2:5: error: unknown function 'visted', did you mean 'visited'?" in err
    assert "target" not in err


@pytest.mark.parametrize(
    "expression, message",
    [
        ("clamp($hp, 0)", "a.wvl:2:11: error: clamp() takes 3 arguments, got 2"),
        ("round($a, 1)", "a.wvl:2:11: error: round() takes 1 argument, got 2"),
        ("random()", "a.wvl:2:11: error: random() takes 2 arguments, got 0"),
        ("min(1)", "a.wvl:2:11: error: min() takes at least 2 arguments, got 1"),
        ("max()", "a.wvl:2:11: error: max() takes at least 2 arguments, got 0"),
        ("visited()", "a.wvl:2:11: error: visited() takes a single node id"),
        ("visit_count($shop)", "a.wvl:2:11: error: visit_count() takes a single node id"),
        ("abs(shop)", "a.wvl:2:15: error: abs() takes numbers, not node id 'shop'"),
        ("sqrt($a)", "a.wvl:2:11: error: unknown function 'sqrt'"),
        ("foo(start)", "a.wvl:2:11: error: unknown function 'foo'"),
    ],
    ids=["too_few", "too_many", "none", "min_one", "max_none", "visited_empty",
         "visit_count_variable", "node_id_for_number", "unknown", "unknown_node_form"],
)
def test_invalid_function_calls_are_errors(tmp_path, capsys, expression, message):
    src = tmp_path / "src"
    _write(src / "a.wvl", f"@node start\n@set $x = {expression}\n@endnode\n")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    err = capsys.readouterr().err
    assert message in err
    assert err.count("error:") == 1


def test_function_call_errors_inside_arguments_are_reported(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@node start\n@set $x = max(clamp(1, 2), visited(gone))\n@endnode\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    err = capsys.readouterr().err
    assert "a.wvl:2:15: error: clamp() takes 3 arguments, got 2" in err
    assert "a.wvl:2:36: error: visited target 'gone' matches no node" in err


def test_visit_functions_build(tmp_path):
    src = tmp_path / "src"
    _write(
        src / "a.wvl",
        "@node start\n@if visited(start) and visit_count(end) < 2\n    @goto end\n@endif\n"
        "@endnode\n",
    )
    _write(src / "b.wvl", "@node end\n@finish\n@endnode\n")

    build_all_files(src, tmp_path / "build", pretty=False)

    data = json.loads((tmp_path / "build" / "a.wvl.json").read_text(encoding="utf-8"))
    condition = data["nodes"][0]["body"][0]["cases"][0]["condition"]
    assert condition == {
        "op": "and",
        "left": {"call": "visited", "node": "start"},
        "right": {"op": "<", "left": {"call": "visit_count", "node": "end"}, "right": 2.0},
    }


def test_all_validation_errors_are_reported_together(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@env\nhp: number\n@endenv\n\n@node a\n@goto gone\n@endnode\n")
    _write(src / "b.wvl", "@env\nhp: number\n@endenv\n\n@node a\nHi.\n@endnode\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    err = capsys.readouterr().err
    assert "duplicate variable 'hp'" in err
    assert "duplicate node id 'a'" in err
    assert "goto target 'gone'" in err


@pytest.mark.parametrize(
    "declaration, message",
    [
        ("a: number(10, 0) = 5", "number 'a' has min 10 greater than max 0"),
        ("a: number(0, 10) = 50", "number 'a' has default 50 above its max 10"),
        ("a: number(5, ) = 0", "number 'a' has default 0 below its min 5"),
        ("a: number(5, )", "number 'a' has implicit default 0 below its min 5"),
        ("a: number(-3, -1) = -4", "number 'a' has default -4 below its min -3"),
    ],
    ids=["min_above_max", "above_max", "below_min", "implicit_below_min", "negative"],
)
def test_invalid_number_range_is_an_error(tmp_path, capsys, declaration, message):
    src = tmp_path / "src"
    _write(src / "a.wvl", f"@env\n{declaration}\n@endenv\n")

    with pytest.raises(typer.Exit) as exc:
        build_all_files(src, tmp_path / "build", pretty=False)

    assert exc.value.exit_code == 1
    assert f"a.wvl:2:1: error: {message}" in capsys.readouterr().err


def test_valid_number_ranges_build(tmp_path):
    src = tmp_path / "src"
    _write(
        src / "a.wvl",
        "@env\n"
        "a: number\n"
        "b: number(0, 1) = 1\n"
        "c: number(-5, 5) = -2.5\n"
        "d: number(, 100)\n"
        "e: number(-10, )\n"
        "f: number(3, 3) = 3\n"
        "@endenv\n",
    )

    build_all_files(src, tmp_path / "build", pretty=False)

    assert (tmp_path / "build" / "env.json").exists()
