"""Integration smoke tests for the installed package and console entry point."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = str(REPO_ROOT / "src")


def _run_toolsmith(*args: str) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = SRC_DIR + os.pathsep + env.get("PYTHONPATH", "")
    return subprocess.run(
        [sys.executable, "-m", "toolsmith.cli", *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def test_installed_entry_point_help():
    """`toolsmith --help` exits 0 and mentions cw when the package is on PYTHONPATH."""
    result = _run_toolsmith("--help")
    assert result.returncode == 0
    assert "toolsmith" in result.stdout
    assert "cw" in result.stdout


def test_installed_entry_point_cw_placeholder():
    """`toolsmith cw` prints the placeholder message and does not mutate git."""
    result = _run_toolsmith("cw")
    assert result.returncode == 0
    assert "not implemented in Phase 1" in result.stdout
    assert "git" not in result.stdout.lower()
