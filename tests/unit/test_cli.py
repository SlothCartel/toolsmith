"""Tests for the CLI entry point, help output, and option parsing."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from toolsmith.cli import create_parser, main
from toolsmith.llm.base import LLMResponse

from .fake_llm import FakeLLMClient


def _make_staged_repo(tmp_path: Path) -> Path:
    """Create a disposable git repository with one staged file."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    (repo / "staged.txt").write_text("staged content")
    subprocess.run(
        ["git", "add", "staged.txt"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    return repo


@pytest.fixture
def fake_llm_client(monkeypatch):
    """Provide a deterministic LLM client so `toolsmith cw` tests need no runtime."""
    client = FakeLLMClient(
        response=LLMResponse(
            text="Fix staged diff detection\n\nUse the cached diff.",
            success=True,
        )
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: client,
    )
    return client


def test_root_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        create_parser().parse_args(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "toolsmith" in captured.out
    assert "cw" in captured.out
    assert "local-first" in captured.out


def test_cw_help_content(capsys):
    with pytest.raises(SystemExit) as exc_info:
        create_parser().parse_args(["cw", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    out = captured.out
    assert "Commit Writer" in out
    assert "staged" in out
    assert "--no-push" in out
    assert "--dry-run" in out
    assert "--model" in out
    assert "git add" in out or "stage" in out
    assert "example" in out.lower()
    assert "Safety" in out or "safety" in out


def test_main_no_args_prints_help(capsys):
    code = main([])
    assert code == 0
    captured = capsys.readouterr()
    assert "toolsmith" in captured.out
    assert "cw" in captured.out


def test_main_cw_no_args_returns_zero(
    capsys, monkeypatch, tmp_path, fake_llm_client
):
    repo = _make_staged_repo(tmp_path)
    monkeypatch.chdir(str(repo))
    monkeypatch.setenv("HOME", str(tmp_path))
    code = main(["cw"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Error" not in captured.err


def test_main_cw_dry_run(capsys, monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    code = main(["cw", "--dry-run"])
    assert code == 0
    captured = capsys.readouterr()
    assert "Dry run" in captured.out
    assert "no commit or push" in captured.out


def test_main_cw_no_push_parses(
    capsys, monkeypatch, tmp_path, fake_llm_client
):
    repo = _make_staged_repo(tmp_path)
    monkeypatch.chdir(str(repo))
    monkeypatch.setenv("HOME", str(tmp_path))
    code = main(["cw", "--no-push"])
    assert code == 0
    assert "Error" not in capsys.readouterr().err


def test_main_cw_model_override_parses(
    capsys, monkeypatch, tmp_path, fake_llm_client
):
    repo = _make_staged_repo(tmp_path)
    monkeypatch.chdir(str(repo))
    monkeypatch.setenv("HOME", str(tmp_path))
    code = main(["cw", "--model", "mistral:latest"])
    assert code == 0
    assert "Error" not in capsys.readouterr().err


def test_main_cw_invalid_toml_exit_code(capsys, monkeypatch, tmp_path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "toolsmith"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text("[[not valid")
    monkeypatch.setenv("HOME", str(home))

    code = main(["cw"])
    captured = capsys.readouterr()
    assert code == 3
    assert "Error:" in captured.err
    assert "Invalid TOML" in captured.err


def test_main_cw_unsupported_provider_exit_code(capsys, monkeypatch, tmp_path):
    home = tmp_path / "home"
    config_dir = home / ".config" / "toolsmith"
    config_dir.mkdir(parents=True)
    (config_dir / "config.toml").write_text(
        """
[llm]
provider = "anthropic"
"""
    )
    monkeypatch.setenv("HOME", str(home))

    code = main(["cw"])
    captured = capsys.readouterr()
    assert code == 3
    assert "Error:" in captured.err
    assert "Unsupported LLM provider" in captured.err


def test_main_cw_keyboard_interrupt_returns_cancel_exit_code(
    monkeypatch, tmp_path
):
    def raise_keyboard_interrupt(_args):
        raise KeyboardInterrupt

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.run", raise_keyboard_interrupt
    )
    code = main(["cw"])
    assert code == 2


def test_main_cw_outside_repository_exits_usage_error(capsys, monkeypatch, tmp_path):
    monkeypatch.chdir(str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    code = main(["cw"])
    assert code == 3
    captured = capsys.readouterr()
    assert "Error:" in captured.err
    assert "git repository" in captured.err.lower()


def test_main_cw_no_staged_changes_exits_usage_error(
    capsys, monkeypatch, tmp_path
):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(
        ["git", "init", "--quiet"],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )
    monkeypatch.chdir(str(repo))
    monkeypatch.setenv("HOME", str(tmp_path))
    code = main(["cw"])
    assert code == 3
    captured = capsys.readouterr()
    assert "Error:" in captured.err
    assert "staged" in captured.err.lower()


def test_main_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "toolsmith" in captured.out
