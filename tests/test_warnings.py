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
        ("@env\nfunc shake()\n@endenv\n", "2:6: warning: function 'shake' is never used"),
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
    ids=["variable", "extern_variable", "function", "function_without_result", "meta_key",
         "empty_pool", "empty_slot", "slot_with_one_node", "priority", "weight", "slot_key"],
)
def test_warnings(tmp_path, capsys, source, expected):
    assert expected in _build_warnings(tmp_path, capsys, source)


def test_unused_character_warns(tmp_path, capsys):
    source = "@env\ncharacter anna\ncharacter ben\n@endenv\n@node a\nben: Hi.\n@endnode\n"

    assert _build_warnings(tmp_path, capsys, source) == [
        "2:11: warning: character 'anna' is never used"
    ]


DIALOGUE_WARNING = "warning: this line looks like dialogue: quote the speaker or write \\: for narration"


@pytest.mark.parametrize(
    "line, expected",
    [
        ("Old Man: Hi.", f"2:8: {DIALOGUE_WARNING}"),
        ("???: Who goes there?", f"2:4: {DIALOGUE_WARNING}"),
        ("Later that night: the village burns.", f"2:17: {DIALOGUE_WARNING}"),
        ("The sign reads: CLOSED.", f"2:15: {DIALOGUE_WARNING}"),
        ("Old {1 + 1} Man: Hi.", f"2:16: {DIALOGUE_WARNING}"),
        ("Signed:", f"2:7: {DIALOGUE_WARNING}"),
        (
            "{friend}: Wait.",
            '2:9: warning: this line looks like dialogue: write friend: or "{friend}": '
            "for a speaker, or \\: for narration",
        ),
        (
            "{anna}: Wait.",
            '2:7: warning: this line looks like dialogue: write anna: or "{anna}": '
            "for a speaker, or \\: for narration",
        ),
        ("{gold}: Coins.", f"2:7: {DIALOGUE_WARNING}"),
        ("{anna}\\: Wait. Old Man: Hi.", None),
        ("The old sign reads: CLOSED.", None),
        ("It was 10:30 when she left.", None),
        ("Old Man\\: Hi.", None),
        ("Day 3\\: The village is quiet.", None),
    ],
    ids=["two_words", "punctuation", "three_words", "third_word", "interpolation",
         "line_end", "variable_hint", "name_hint", "number_variable",
         "escaped_after_interpolation",
         "fourth_word", "no_space", "escaped", "escaped_second_word"],
)
def test_narration_that_looks_like_dialogue_warns(tmp_path, capsys, line, expected):
    source = (
        f"@node a\n{line}\n@endnode\n"
        "@env\ncharacter anna\nvar friend: character = anna\nvar gold: number\n@endenv\n"
    )
    warnings = [w for w in _build_warnings(tmp_path, capsys, source) if "dialogue" in w]

    assert warnings == ([] if expected is None else [expected])


@pytest.mark.parametrize(
    "source",
    [
        "@env\nvar energy: number = 10  # weavly: ignore\n@endenv\n",
        "@env\npool hub_10 #weavly:ignore\n@endenv\n",
        "@env\nslot bob # weavly: ignore\n@endenv\n",
        "@env\nmeta cost: number # weavly: ignore\n@endenv\n",
        "@node a\n@meta\npriority: 1  # weavly: ignore\n@endmeta\n@endnode\n",
    ],
    ids=["variable", "pool", "slot", "meta_key", "meta_entry"],
)
def test_ignore_comment_silences_its_line(tmp_path, capsys, source):
    assert _build_warnings(tmp_path, capsys, source) == []


@pytest.mark.parametrize(
    "source, expected",
    [
        (
            "@env\nvar gold: number  # weavly: ignore\n@endenv\n@node a\n@increase gold\n@endnode\n",
            "2:19: warning: weavly: ignore silences no warning",
        ),
        (
            "@env\n# weavly: ignore\nvar gold: number\n@endenv\n",
            "2:1: warning: weavly: ignore silences no warning",
        ),
    ],
    ids=["used_variable", "own_line"],
)
def test_ignore_that_silences_nothing_warns(tmp_path, capsys, source, expected):
    assert expected in _build_warnings(tmp_path, capsys, source)


def test_ignore_counts_lines_like_the_parser(tmp_path, capsys):
    source = (
        "@node a\nHi there.\n@endnode\n"
        "@env\nvar gold: number  # weavly: ignore\n@endenv\n"
    )

    assert _build_warnings(tmp_path, capsys, source) == []


def test_ignore_is_text_on_narration_lines(tmp_path, capsys):
    source = "@node a\nOld Man: Hi. # weavly: ignore\n@endnode\n"

    assert _build_warnings(tmp_path, capsys, source) == [f"2:8: {DIALOGUE_WARNING}"]


def test_ignore_in_a_string_is_not_a_comment(tmp_path, capsys):
    source = '@env\nvar s: string = "# weavly: ignore"\n@endenv\n'

    assert _build_warnings(tmp_path, capsys, source) == [
        "2:5: warning: variable 's' is never used"
    ]


def test_ignore_only_applies_to_its_own_file(tmp_path, capsys):
    src = tmp_path / "src"
    _write(src / "a.wvl", "@env\nvar gold: number\n@endenv\n")
    _write(src / "b.wvl", "@env\nvar day: number  # weavly: ignore\n@endenv\n")

    build_all_files(src, tmp_path / "build", pretty=False)

    assert "a.wvl:2:5: warning: variable 'gold' is never used" in capsys.readouterr().err


def test_used_declarations_have_no_warnings(tmp_path, capsys):
    source = (
        "@env\n"
        "extern var day: number\n"
        "func trust(): number\n"
        "func shake()\n"
        "meta cost: number\n"
        "meta art: string\n"
        "pool city\n"
        "slot bob\n"
        "character guide\n"
        "var gold: number\n"
        "var name: string\n"
        "@endenv\n"
        "@node a\n"
        "@meta\npool: city\nslot: bob\npriority: 1\nweight: 2\ncost: 3\n@endmeta\n"
        "@do shake()\n"
        "@increase gold\n"
        "guide: Day {day}, trust {trust()}, art {.art}, name {name}.\n"
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
