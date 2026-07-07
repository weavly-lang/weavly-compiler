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
