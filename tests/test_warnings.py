import pytest
import typer

from weavly.parsing import build_all_files


def _write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _build_warnings(tmp_path, capsys, source):
    src = tmp_path / "src"
    _write(src / "a.wvl", source)

    build_all_files(src, tmp_path / "build", pretty=False)

    out, err = capsys.readouterr()
    assert out == ""
    return [line.split("a.wvl:", 1)[1] for line in err.splitlines()]


@pytest.mark.parametrize(
    "source, expected",
    [
        ("@env\nvar gold: number\n@endenv\n", "2:5: warning: variable 'gold' is never used"),
        ("@env\nextern var day: number\n@endenv\n", "2:12: warning: variable 'day' is never used"),
        ("@env\nfunc trust(): number\n@endenv\n", "2:6: warning: function 'trust' is never used"),
        ("@env\ncommand shake()\n@endenv\n", "2:9: warning: command 'shake' is never used"),
        (
            "@env\nmeta cost: number\n@endenv\n",
            "2:6: warning: meta key 'cost' is never written or read",
        ),
        ("@env\npool harbor\n@endenv\n", "2:6: warning: pool 'harbor' has no nodes"),
        ("@env\nslot bob\n@endenv\n", "2:6: warning: slot 'bob' has no nodes"),
        (
            "@env\npool city\nslot bob\n@endenv\n"
            "@node a\n@meta\npool: city\nslot: bob\n@endmeta\n@endnode\n",
            "3:6: warning: slot 'bob' has only one node",
        ),
        (
            "@node a\n@meta\npriority: 1\n@endmeta\n@endnode\n",
            "3:1: warning: priority has no effect on a node in no pool",
        ),
        (
            "@node a\n@meta\nweight: 2\n@endmeta\n@endnode\n",
            "3:1: warning: weight has no effect on a node in no pool",
        ),
        (
            "@env\nslot bob\n@endenv\n"
            "@node a\n@meta\nslot: bob\n@endmeta\n@endnode\n"
            "@node b\n@meta\nslot: bob\n@endmeta\n@endnode\n",
            "6:1: warning: slot has no effect on a node in no pool",
        ),
    ],
    ids=["variable", "extern_variable", "function", "command", "meta_key", "empty_pool", "empty_slot",
         "slot_with_one_node", "priority", "weight", "slot_key"],
)
def test_warnings(tmp_path, capsys, source, expected):
    assert expected in _build_warnings(tmp_path, capsys, source)


def test_used_declarations_have_no_warnings(tmp_path, capsys):
    source = (
        "@env\n"
        "extern var day: number\n"
        "func trust(): number\n"
        "command shake()\n"
        "meta cost: number\n"
        "meta art: string\n"
        "pool city\n"
        "slot bob\n"
        "var gold: number\n"
        "var name: string\n"
        "@endenv\n"
        "@node a\n"
        "@meta\npool: city\nslot: bob\npriority: 1\nweight: 2\ncost: 3\n@endmeta\n"
        "@shake\n"
        "@increase $gold\n"
        "$name: Day {$day}, trust {trust()}, art {meta(art)}.\n"
        "@endnode\n"
        "@node b\n"
        "@meta\npool: city\nslot: bob\n@endmeta\n"
        "@endnode\n"
    )

    assert _build_warnings(tmp_path, capsys, source) == []


def test_warnings_do_not_fail_the_build(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@env\npool harbor\n@endenv\n@node a\nHi.\n@endnode\n")

    build_all_files(src, tmp_path / "build", pretty=False)

    assert (tmp_path / "build" / "a.wvl.json").is_file()
    assert "warning: pool 'harbor' has no nodes" in capsys.readouterr().err


def test_warnings_are_not_printed_when_the_build_fails(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@env\npool harbor\n@endenv\n@node a\n@jump gone\n@endnode\n")

    with pytest.raises(typer.Exit):
        build_all_files(src, tmp_path / "build", pretty=False)

    err = capsys.readouterr().err
    assert "error: jump target 'gone' matches no node" in err
    assert "warning:" not in err
