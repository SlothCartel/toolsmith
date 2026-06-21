"""Integration smoke tests for the installed package and console entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = str(REPO_ROOT / "src")


def _run_toolsmith(*args: str, cwd: str | None = None) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "toolsmith.cli", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
        cwd=cwd,
    )


def _make_staged_repo(tmp_path: Path) -> Path:
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


def test_installed_entry_point_help():
    """`toolsmith --help` exits 0 and mentions cw when the package is on PYTHONPATH."""
    result = _run_toolsmith("--help")
    assert result.returncode == 0
    assert "toolsmith" in result.stdout
    assert "cw" in result.stdout


def test_installed_entry_point_cw_dry_run(tmp_path):
    """`toolsmith cw --dry-run` exits cleanly without requiring a provider."""
    repo = _make_staged_repo(tmp_path)
    result = _run_toolsmith("cw", "--dry-run", cwd=str(repo))
    assert result.returncode == 0
    assert "Dry run" in result.stdout


def test_installed_entry_point_cw_outside_repository_exits_nonzero(tmp_path):
    """`toolsmith cw` exits with an actionable error when not inside a repository."""
    result = _run_toolsmith("cw", cwd=str(tmp_path))
    assert result.returncode == 3
    assert "Error:" in result.stderr
    assert "git repository" in result.stderr.lower()
