"""Git repository detection and root resolution (Phase 3)."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path


from toolsmith.errors import DependencyError, GitError, NoRepositoryError


def _git_env() -> dict[str, str]:
    """Return an environment that disables pagers and fixes locale for parsing."""
    env = os.environ.copy()
    env["GIT_PAGER"] = "cat"
    env["LC_ALL"] = "C"
    return env


def _run_git(
    cwd: Path | str,
    *args: str,
    check: bool = True,
) -> subprocess.CompletedProcess[str]:
    """Run a git subprocess using argument arrays, never shell interpolation.

    Raises:
        DependencyError: When the git executable cannot be found.
        GitError: When *check* is True and the command exits non-zero.
    """
    command = ["git", *args]
    try:
        result = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env=_git_env(),
        )
    except FileNotFoundError as exc:
        git_path = shutil.which("git") or "git"
        raise DependencyError(
            f"Git executable not found ({git_path}). Is git installed and on PATH?"
        ) from exc

    if check and result.returncode != 0:
        stderr = result.stderr.strip()
        command_str = " ".join(command)
        message = f"Git command failed: {command_str}"
        if stderr:
            message = f"{message}\n{stderr}"
        raise GitError(message)

    return result


def find_repository_root(start_path: Path | str | None = None) -> Path:
    """Resolve the git repository root for *start_path* (default: cwd).

    The resolution is consistent regardless of which subdirectory the caller
    is in, because git resolves paths relative to the repository root.

    Raises:
        NoRepositoryError: When *start_path* is not inside a git repository.
        GitError: When the git command itself fails for another reason.
    """
    cwd = Path(start_path) if start_path is not None else Path.cwd()
    result = _run_git(cwd, "rev-parse", "--show-toplevel", check=False)

    if result.returncode != 0:
        stderr = result.stderr.strip()
        lowered = stderr.lower()
        if "not a git repository" in lowered or "outside repository" in lowered:
            raise NoRepositoryError(
                f"Not inside a git repository (cwd: {cwd.resolve()}). "
                "Run `git init` or change to a repository directory."
            )
        raise GitError(
            f"Git command failed: git rev-parse --show-toplevel\n{stderr}"
        )

    root = Path(result.stdout.strip()).resolve()
    return root
