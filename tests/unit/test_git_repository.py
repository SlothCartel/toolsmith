"""Unit tests for the git subprocess runner and repository root resolution."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from toolsmith.errors import DependencyError, GitError, NoRepositoryError
from toolsmith.git import repository


def test_run_git_uses_argument_array_and_no_shell():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("/repo\n", returncode=0)
        repository._run_git("/some/path", "rev-parse", "--show-toplevel")

    mock_run.assert_called_once()
    call = mock_run.call_args
    assert call.args[0] == ["git", "rev-parse", "--show-toplevel"]
    assert call.kwargs.get("shell") is None or call.kwargs.get("shell") is False
    assert call.kwargs["capture_output"] is True


def test_run_git_disables_pager_and_sets_locale():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("/repo\n", returncode=0)
        repository._run_git("/some/path", "status")

    env = mock_run.call_args.kwargs["env"]
    assert env["GIT_PAGER"] == "cat"
    assert env["LC_ALL"] == "C"


def test_run_git_maps_filenotfound_to_dependency_error():
    with patch("subprocess.run", side_effect=FileNotFoundError("git")):
        with pytest.raises(DependencyError) as exc_info:
            repository._run_git("/some/path", "status")
    assert "Git executable not found" in str(exc_info.value)


def test_run_git_maps_nonzero_to_git_error_with_stderr():
    with patch("subprocess.run") as mock_run:
        mock_run.return_value = _completed("", returncode=1, stderr="fatal: bad object")
        with pytest.raises(GitError) as exc_info:
            repository._run_git("/some/path", "bad-command")
    assert "git bad-command" in str(exc_info.value)
    assert "fatal: bad object" in str(exc_info.value)


def test_find_repository_root_returns_resolved_path():
    with patch.object(repository, "_run_git") as mock_run:
        mock_run.return_value = _completed("/home/user/project\n", returncode=0)
        root = repository.find_repository_root("/home/user/project/src")
    assert root == Path("/home/user/project").resolve()
    mock_run.assert_called_once_with(
        Path("/home/user/project/src"), "rev-parse", "--show-toplevel", check=False
    )


def test_find_repository_root_outside_repo_raises_no_repository_error():
    with patch.object(repository, "_run_git") as mock_run:
        mock_run.return_value = _completed(
            "",
            returncode=128,
            stderr="fatal: not a git repository (or any of the parent directories): .git",
        )
        with pytest.raises(NoRepositoryError):
            repository.find_repository_root("/tmp")


def test_find_repository_root_git_failure_raises_git_error():
    with patch.object(repository, "_run_git") as mock_run:
        mock_run.return_value = _completed(
            "", returncode=128, stderr="fatal: unable to read HEAD"
        )
        with pytest.raises(GitError) as exc_info:
            repository.find_repository_root("/tmp")
    assert "rev-parse --show-toplevel" in str(exc_info.value)


def _completed(
    stdout: str, returncode: int = 0, stderr: str = ""
) -> MagicMock:
    result = MagicMock()
    result.stdout = stdout
    result.stderr = stderr
    result.returncode = returncode
    return result
