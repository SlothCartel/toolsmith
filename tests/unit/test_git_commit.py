"""Unit tests for the git commit and push services."""

from __future__ import annotations

from pathlib import Path

from toolsmith.git import commit as git_commit
from toolsmith.git.repository import _run_git


def _init_repo(tmp_path: Path, *, set_identity: bool = True) -> Path:
    """Create an initialized git repository with optional user identity."""
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q", check=True)
    if set_identity:
        _run_git(repo, "config", "user.email", "test@example.com", check=True)
        _run_git(repo, "config", "user.name", "Test User", check=True)
    return repo


def _write_and_stage(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    _run_git(repo, "add", path, check=True)


class TestGitCommitService:
    def test_creates_commit_with_message_file(self, tmp_path):
        repo = _init_repo(tmp_path)
        _write_and_stage(repo, "file.txt", "hello")

        service = git_commit.GitCommitService()
        result = service.create_commit(repository_root=repo, message="Add greeting")

        assert result.success is True
        head_message = _run_git(repo, "log", "-1", "--pretty=%B", check=True).stdout.strip()
        assert head_message == "Add greeting"

    def test_preserves_staged_index_without_staging_unstaged_changes(self, tmp_path):
        repo = _init_repo(tmp_path)
        _write_and_stage(repo, "staged.txt", "staged content")
        (repo / "unstaged.txt").write_text("do not commit")

        service = git_commit.GitCommitService()
        result = service.create_commit(repository_root=repo, message="Add staged file")

        assert result.success is True
        committed_files = _run_git(
            repo, "ls-tree", "-r", "HEAD", "--name-only", check=True
        ).stdout.splitlines()
        assert "staged.txt" in committed_files
        assert "unstaged.txt" not in committed_files
        # Unstaged file remains in the working tree.
        assert (repo / "unstaged.txt").exists()

    def test_commit_failure_returns_useful_stderr(self, tmp_path, monkeypatch):
        """Missing user identity makes git commit fail with actionable stderr."""
        # Isolate from any global git identity so the commit fails deterministically.
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
        monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
        repo = _init_repo(tmp_path, set_identity=False)
        _write_and_stage(repo, "file.txt", "hello")

        service = git_commit.GitCommitService()
        result = service.create_commit(repository_root=repo, message="Add greeting")

        assert result.success is False
        assert "email" in result.message.lower() or "identity" in result.message.lower()
        # No commit should have been created.
        log_result = _run_git(repo, "log", "--oneline", check=False)
        assert log_result.returncode != 0 or log_result.stdout.strip() == ""

    def test_failing_commit_hook_blocks_commit(self, tmp_path):
        repo = _init_repo(tmp_path)
        hook = repo / ".git" / "hooks" / "commit-msg"
        hook.write_text("#!/bin/sh\nexit 1\n")
        hook.chmod(0o755)
        _write_and_stage(repo, "file.txt", "hello")

        service = git_commit.GitCommitService()
        result = service.create_commit(repository_root=repo, message="Add greeting")

        assert result.success is False
        assert result.message != ""
        head_result = _run_git(repo, "log", "--oneline", check=False)
        assert head_result.returncode != 0 or head_result.stdout.strip() == ""

    def test_no_hook_bypass_or_signing_flags(self, tmp_path, monkeypatch):
        """The service must invoke only `git commit -F <file>`."""
        repo = _init_repo(tmp_path)
        _write_and_stage(repo, "file.txt", "hello")

        captured_args: list[list[str]] = []

        def fake_run_git(cwd, *args, check=True):
            captured_args.append(list(args))
            # Return a fake success to keep the test focused on arguments.
            class _Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return _Result()

        monkeypatch.setattr(
            "toolsmith.git.commit._run_git",
            fake_run_git,
        )

        service = git_commit.GitCommitService()
        service.create_commit(repository_root=repo, message="Add greeting")

        assert captured_args
        commit_args = captured_args[0]
        assert len(commit_args) == 3
        assert commit_args[:2] == ["commit", "-F"]
        assert Path(commit_args[2]).exists() is False  # temp file already cleaned up

    def test_temporary_message_file_is_cleaned_up_on_success(self, tmp_path):
        repo = _init_repo(tmp_path)
        _write_and_stage(repo, "file.txt", "hello")

        before = {p.name for p in tmp_path.glob("toolsmith-commit-message-*")}
        service = git_commit.GitCommitService()
        result = service.create_commit(repository_root=repo, message="Add greeting")

        assert result.success is True
        after = {p.name for p in tmp_path.glob("toolsmith-commit-message-*")}
        assert after == before

    def test_temporary_message_file_is_cleaned_up_on_failure(self, tmp_path, monkeypatch):
        # Isolate from global identity so the commit fails deterministically.
        monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
        monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
        repo = _init_repo(tmp_path, set_identity=False)
        _write_and_stage(repo, "file.txt", "hello")

        before = {p.name for p in tmp_path.glob("toolsmith-commit-message-*")}
        service = git_commit.GitCommitService()
        result = service.create_commit(repository_root=repo, message="Add greeting")

        assert result.success is False
        after = {p.name for p in tmp_path.glob("toolsmith-commit-message-*")}
        assert after == before


class TestGitPushService:
    def test_pushes_to_local_bare_remote(self, tmp_path):
        origin = tmp_path / "origin.git"
        origin.mkdir()
        _run_git(origin, "init", "--bare", "-q", check=True)

        repo = _init_repo(tmp_path)
        _run_git(repo, "remote", "add", "origin", str(origin), check=True)
        _write_and_stage(repo, "file.txt", "hello")
        _run_git(repo, "commit", "-m", "initial", check=True)

        service = git_commit.GitPushService()
        result = service.push(repository_root=repo)

        assert result.success is True
        pushed_commits = _run_git(origin, "log", "--oneline", check=True).stdout.strip()
        assert "initial" in pushed_commits

    def test_push_failure_returns_useful_stderr(self, tmp_path):
        repo = _init_repo(tmp_path)
        _write_and_stage(repo, "file.txt", "hello")
        _run_git(repo, "commit", "-m", "initial", check=True)
        # No remote configured; push will fail.

        service = git_commit.GitPushService()
        result = service.push(repository_root=repo)

        assert result.success is False
        assert "remote" in result.message.lower() or "upstream" in result.message.lower()

    def test_ordinary_push_has_no_force_flags(self, tmp_path, monkeypatch):
        repo = _init_repo(tmp_path)

        captured_args: list[list[str]] = []

        def fake_run_git(cwd, *args, check=True):
            captured_args.append(list(args))

            class _Result:
                returncode = 0
                stdout = ""
                stderr = ""
            return _Result()

        monkeypatch.setattr(
            "toolsmith.git.commit._run_git",
            fake_run_git,
        )

        service = git_commit.GitPushService()
        service.push(repository_root=repo)

        assert captured_args
        push_args = captured_args[0]
        assert push_args == ["push"]



def test_temporary_message_file_contains_only_message(tmp_path, monkeypatch):
    """The secure temp file used for `git commit -F` holds only the message."""
    repo = _init_repo(tmp_path)
    _write_and_stage(repo, "file.txt", "hello")

    captured: dict[str, object] = {}

    def fake_run_git(cwd, *args, check=True):
        assert args[:2] == ("commit", "-F")
        message_file = Path(args[2])
        assert message_file.exists()
        contents = message_file.read_text(encoding="utf-8")
        captured["contents"] = contents
        captured["message_file"] = str(message_file)

        class _Result:
            returncode = 0
            stdout = ""
            stderr = ""
        return _Result()

    monkeypatch.setattr("toolsmith.git.commit._run_git", fake_run_git)

    message = """Add greeting

Detailed body."""
    service = git_commit.GitCommitService()
    result = service.create_commit(repository_root=repo, message=message)

    assert result.success is True
    assert captured["contents"] == message
    # Staged diff data must never be written into the commit-message file.
    assert "diff" not in captured["contents"].lower()
    assert "@@" not in captured["contents"]
    assert "Binary files" not in captured["contents"]
    # The file is cleaned up by the service.
    assert not Path(captured["message_file"]).exists()
