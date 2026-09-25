import re
from importlib.metadata import version

from typer.testing import CliRunner

from weavly.cli import app

runner = CliRunner()


def _plain(text):
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def test_init_creates_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert result.stdout == "Created src/nodes.wvl\n"
    assert (tmp_path / "src" / "nodes.wvl").is_file()


def test_init_named_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "my-project"])

    assert result.exit_code == 0
    assert result.stdout == "Created my-project/src/nodes.wvl\n"
    assert (tmp_path / "my-project" / "src" / "nodes.wvl").is_file()


def test_init_creates_missing_parent_directories(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init", "games/my-project"])

    assert result.exit_code == 0
    assert (tmp_path / "games" / "my-project" / "src" / "nodes.wvl").is_file()


def test_init_refuses_existing_src(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "story.wvl").write_text("keep", encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert result.stdout == ""
    assert "error: directory 'src' already exists" in result.stderr
    assert (tmp_path / "src" / "story.wvl").read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "src" / "nodes.wvl").exists()


def test_build_reports_file_count(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])
    (tmp_path / "src" / "more.wvl").write_text(
        "@node more\nHi.\n@endnode\n", encoding="utf-8"
    )

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 0
    assert result.stdout == "Built 2 files into build/\n"
    assert (tmp_path / "build" / "env.json").is_file()


def test_build_pretty_flag(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    runner.invoke(app, ["init"])

    result = runner.invoke(app, ["build", "--pretty"])

    assert result.exit_code == 0
    assert result.stdout == "Built 1 file into build/\n"
    assert "\n  " in (tmp_path / "build" / "env.json").read_text(encoding="utf-8")


def test_failed_build_prints_no_success_message(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["build"])

    assert result.exit_code == 1
    assert result.stdout == ""


def test_help_describes_commands():
    result = runner.invoke(app, ["--help"])
    output = _plain(result.stdout)

    assert result.exit_code == 0
    assert "Compile src/**/*.wvl into build/." in output
    assert "Create a new Weavly project" in output
    assert "--install-completion" not in output


def test_build_help_has_plain_pretty_flag():
    result = runner.invoke(app, ["build", "--help"])
    output = _plain(result.stdout)

    assert result.exit_code == 0
    assert "--pretty" in output
    assert "--no-pretty" not in output


def test_version_flag():
    result = runner.invoke(app, ["--version"])

    assert result.exit_code == 0
    assert result.stdout == f"weavly {version('weavly')}\n"
