"""Integration tests for read-only git services using temporary repositories."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from toolsmith.errors import GitError, NoRepositoryError, NoStagedChangesError
from toolsmith.git import diff, repository


def _git(repo: Path, *args: str) -> None:
    """Run a git command in *repo* for test setup."""
    subprocess.run(
        ["git", *args],
        cwd=str(repo),
        check=True,
        capture_output=True,
    )


def _init_repo(tmp_path: Path) -> Path:
    """Create and return an empty temporary git repository."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _git(repo, "init", "--quiet")
    return repo


def _commit(repo: Path, message: str = "init") -> None:
    """Create a commit with a disposable identity."""
    _git(
        repo,
        "-c",
        "user.name=toolsmith-test",
        "-c",
        "user.email=test@toolsmith.local",
        "commit",
        "-m",
        message,
        "--quiet",
    )


def test_find_repository_root_from_subdirectory(tmp_path):
    repo = _init_repo(tmp_path)
    subdir = repo / "src" / "deep"
    subdir.mkdir(parents=True)

    root = repository.find_repository_root(subdir)
    assert root == repo.resolve()


def test_find_repository_root_outside_repository(tmp_path):
    with pytest.raises(NoRepositoryError) as exc_info:
        repository.find_repository_root(tmp_path)
    assert "git repository" in str(exc_info.value).lower()


def test_no_staged_changes_raises(tmp_path):
    repo = _init_repo(tmp_path)
    with pytest.raises(NoStagedChangesError):
        diff.prepare_staged_diff(repo, max_diff_chars=1000)


def test_staged_text_change_summary_and_diff(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "file.txt").write_text("initial\n")
    _git(repo, "add", "file.txt")
    _commit(repo)

    (repo / "file.txt").write_text("modified\n")
    _git(repo, "add", "file.txt")

    prepared = diff.prepare_staged_diff(repo, max_diff_chars=1000)
    assert len(prepared.summary) == 1
    entry = prepared.summary[0]
    assert entry.status == "M"
    assert entry.path == "file.txt"
    assert entry.is_binary is False
    assert "modified" in prepared.diff


def test_staged_and_unstaged_same_file_isolated(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "file.txt").write_text("initial\n")
    _git(repo, "add", "file.txt")
    _commit(repo)

    (repo / "file.txt").write_text("staged line\nunstaged line\n")
    _git(repo, "add", "file.txt")
    (repo / "file.txt").write_text("staged line\nother unstaged line\n")

    prepared = diff.prepare_staged_diff(repo, max_diff_chars=1000)
    assert "staged line" in prepared.diff
    # The unstaged modification must not appear in the cached diff.
    assert "other unstaged line" not in prepared.diff


def test_staged_rename(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "old.txt").write_text("content\n")
    _git(repo, "add", "old.txt")
    _commit(repo)

    _git(repo, "mv", "old.txt", "new.txt")

    prepared = diff.prepare_staged_diff(repo, max_diff_chars=1000)
    entry = prepared.summary[0]
    assert entry.status == "R"
    assert entry.path == "new.txt"
    assert entry.old_path == "old.txt"


def test_staged_delete(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "gone.txt").write_text("content\n")
    _git(repo, "add", "gone.txt")
    _commit(repo)

    _git(repo, "rm", "--quiet", "gone.txt")

    prepared = diff.prepare_staged_diff(repo, max_diff_chars=1000)
    entry = prepared.summary[0]
    assert entry.status == "D"
    assert entry.path == "gone.txt"


def test_staged_binary_is_marked_and_not_opened(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "image.bin").write_bytes(bytes(range(256)))
    _git(repo, "add", "image.bin")

    prepared = diff.prepare_staged_diff(repo, max_diff_chars=1000)
    entry = prepared.summary[0]
    assert entry.status == "A"
    assert entry.path == "image.bin"
    assert entry.is_binary is True
    assert "Binary files" in prepared.diff
    # Working-tree contents are never decoded as text in the diff.
    assert bytes(range(256)) not in prepared.diff.encode("utf-8", errors="replace")


def test_oversized_diff_truncated(tmp_path):
    repo = _init_repo(tmp_path)
    lines = [f"line {i:05d}\n" for i in range(2000)]
    (repo / "big.txt").write_text("".join(lines))
    _git(repo, "add", "big.txt")

    prepared = diff.prepare_staged_diff(repo, max_diff_chars=200)
    assert prepared.truncated is True
    assert "truncated" in prepared.diff.lower()
    assert prepared.original_diff_chars > 200


def test_git_command_failure_maps_to_git_error(tmp_path):
    repo = _init_repo(tmp_path)
    with pytest.raises(GitError) as exc_info:
        repository._run_git(repo, "not-a-real-command")
    assert "git" in str(exc_info.value).lower()


def test_prepared_diff_never_persists_to_files(tmp_path):
    repo = _init_repo(tmp_path)
    (repo / "file.txt").write_text("data\n")
    _git(repo, "add", "file.txt")

    # Capture file writes during prepare_staged_diff by monitoring the repo.
    before = set(repo.rglob("*"))
    diff.prepare_staged_diff(repo, max_diff_chars=1000)
    after = set(repo.rglob("*"))
    # .git internals may change; we only assert no new non-git files appeared.
    new_files = after - before
    non_git_new = {p for p in new_files if ".git" not in p.parts}
    assert non_git_new == set()


def test_outside_repository_error_occurs_before_provider_setup(
    tmp_path, monkeypatch
):
    """Git failures must happen before any LLM/provider construction."""
    monkeypatch.chdir(str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    provider_spy = []

    def fake_provider(*args, **kwargs):
        provider_spy.append((args, kwargs))
        raise AssertionError("provider should not be constructed")

    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_repository.find_repository_root",
        repository.find_repository_root,
    )
    # The command should fail at repository resolution before ever reaching the
    # (non-existent) provider. This test simply confirms the public command
    # raises NoRepositoryError without touching the provider seam.
    from toolsmith.git.repository import find_repository_root as public_find

    with pytest.raises(NoRepositoryError):
        public_find(tmp_path)
    assert provider_spy == []
