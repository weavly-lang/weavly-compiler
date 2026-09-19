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
    assert globals_json == {"nodes": []}

    witch_json = json.loads(
        (build / "scenes" / "witch.wvl.json").read_text(encoding="utf-8")
    )
    assert "declarations" not in witch_json
    assert witch_json["nodes"][0]["id"] == "witch"


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
