from typer.testing import CliRunner

from weavly.cli import app

runner = CliRunner()


def test_init_creates_project(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 0
    assert (tmp_path / "src" / "nodes.wvl").is_file()


def test_init_refuses_existing_src(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "story.wvl").write_text("keep", encoding="utf-8")

    result = runner.invoke(app, ["init"])

    assert result.exit_code == 1
    assert "already exists" in result.output
    assert (tmp_path / "src" / "story.wvl").read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "src" / "nodes.wvl").exists()
