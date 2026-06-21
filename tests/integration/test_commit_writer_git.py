"""Integration tests for Commit Writer real git mutation.

Every test creates and destroys its own temporary git repository. The toolsmith
worktree is never mutated. LLM calls and terminal input are mocked; real git
commit/push services are exercised unless the test is specifically probing the
prompt boundary.
"""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import patch

import pytest

from toolsmith.commands import commit_writer
from toolsmith.errors import CancelError, PushError
from toolsmith.git import commit as git_commit
from toolsmith.git.repository import _run_git
from toolsmith.llm.base import LLMClient, LLMRequest, LLMResponse


class FakeLLMClient(LLMClient):
    """In-memory LLM client that records requests and returns a fixed response."""

    def __init__(self, response: LLMResponse | None = None) -> None:
        self.response = response or LLMResponse(
            text="fake generated commit message", success=True
        )
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return self.response


def _make_args(
    *, no_push: bool = False, dry_run: bool = False, model: str | None = None
) -> argparse.Namespace:
    return argparse.Namespace(no_push=no_push, dry_run=dry_run, model=model)


def _init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    _run_git(repo, "init", "-q", check=True)
    _run_git(repo, "config", "user.email", "test@example.com", check=True)
    _run_git(repo, "config", "user.name", "Test User", check=True)
    return repo


def _write_and_stage(repo: Path, path: str, content: str) -> None:
    target = repo / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content)
    _run_git(repo, "add", path, check=True)


@pytest.fixture
def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient(
        response=LLMResponse(
            text="Add sample file\n\nStage and commit the sample.",
            success=True,
        )
    )


@pytest.fixture
def patched_repo(monkeypatch, tmp_path, fake_llm_client):
    """Create a temp repo, stage a file, and point the command at it."""
    repo = _init_repo(tmp_path)
    _write_and_stage(repo, "sample.txt", "sample content")

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_repository.find_repository_root",
        lambda: repo,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: fake_llm_client,
    )
    return repo


class TestCommitFlow:
    def test_accept_creates_real_commit(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("toolsmith.ui.prompts.input", side_effect=["a", ""]):
            code = commit_writer.run(
                _make_args(),
                commit_service=git_commit.GitCommitService(),
                push_service=git_commit.NoopPushService(),
            )

        assert code == 0
        head_message = _run_git(
            patched_repo, "log", "-1", "--pretty=%B", check=True
        ).stdout.strip()
        assert head_message == "Add sample file\n\nStage and commit the sample."

    def test_edited_message_is_committed(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        edited = "Edited subject\n\nEdited body."

        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.editor.edit_message",
            lambda message: edited,
        )

        with patch("toolsmith.ui.prompts.input", side_effect=["e", "a", ""]):
            code = commit_writer.run(
                _make_args(no_push=True),
                commit_service=git_commit.GitCommitService(),
            )

        assert code == 0
        head_message = _run_git(
            patched_repo, "log", "-1", "--pretty=%B", check=True
        ).stdout.strip()
        assert head_message == edited

    def test_reject_creates_no_commit(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("toolsmith.ui.prompts.input", side_effect=["r"]), pytest.raises(
            CancelError
        ):
            commit_writer.run(
                _make_args(),
                commit_service=git_commit.GitCommitService(),
            )

        log_result = _run_git(patched_repo, "log", "--oneline", check=False)
        assert log_result.returncode != 0 or log_result.stdout.strip() == ""

    def test_keyboard_interrupt_before_approval_creates_no_commit(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "toolsmith.ui.prompts.input", side_effect=KeyboardInterrupt()
        ), pytest.raises(KeyboardInterrupt):
            commit_writer.run(
                _make_args(),
                commit_service=git_commit.GitCommitService(),
            )

        log_result = _run_git(patched_repo, "log", "--oneline", check=False)
        assert log_result.returncode != 0 or log_result.stdout.strip() == ""

    def test_dry_run_creates_no_commit_and_no_push_prompt(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        # If input were called, this side_effect would raise and fail the test.
        with patch(
            "toolsmith.ui.prompts.input", side_effect=["a"]
        ):
            code = commit_writer.run(_make_args(dry_run=True))

        assert code == 0
        log_result = _run_git(patched_repo, "log", "--oneline", check=False)
        assert log_result.returncode != 0 or log_result.stdout.strip() == ""

    def test_no_push_creates_commit_without_push_prompt(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch(
            "toolsmith.ui.prompts.input", side_effect=["a"]
        ):
            code = commit_writer.run(
                _make_args(no_push=True),
                commit_service=git_commit.GitCommitService(),
            )

        assert code == 0
        log_result = _run_git(patched_repo, "log", "--oneline", check=True)
        assert "Add sample" in log_result.stdout

    def test_unstaged_changes_are_not_committed(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        (patched_repo / "unstaged.txt").write_text("leave me alone")

        with patch("toolsmith.ui.prompts.input", side_effect=["a", ""]):
            code = commit_writer.run(
                _make_args(no_push=True),
                commit_service=git_commit.GitCommitService(),
            )

        assert code == 0
        committed_files = _run_git(
            patched_repo, "ls-tree", "-r", "HEAD", "--name-only", check=True
        ).stdout.splitlines()
        assert "sample.txt" in committed_files
        assert "unstaged.txt" not in committed_files
        assert (patched_repo / "unstaged.txt").exists()


class TestPushPromptFlow:
    def test_push_prompt_default_no_on_enter(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        with patch("toolsmith.ui.prompts.input", side_effect=["a", ""]):
            code = commit_writer.run(
                _make_args(),
                commit_service=git_commit.GitCommitService(),
                push_service=git_commit.NoopPushService(),
            )

        assert code == 0
        head = _run_git(patched_repo, "log", "-1", "--oneline", check=True).stdout.strip()
        assert "Add sample" in head

    def test_push_prompt_explicit_yes_calls_push_service(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        push_service = git_commit.NoopPushService()

        with patch("toolsmith.ui.prompts.input", side_effect=["a", "y"]):
            code = commit_writer.run(
                _make_args(),
                commit_service=git_commit.GitCommitService(),
                push_service=push_service,
            )

        assert code == 0
        assert len(push_service.calls) == 1
        assert push_service.calls[0]["repository_root"] == patched_repo

    def test_push_failure_does_not_roll_back_commit(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        class FailingPushService(git_commit.PushService):
            def push(self, *, repository_root: Path) -> git_commit.PushResult:
                return git_commit.PushResult(
                    success=False, message="no upstream configured"
                )

        with patch("toolsmith.ui.prompts.input", side_effect=["a", "y"]), pytest.raises(
            PushError
        ) as exc_info:
            commit_writer.run(
                _make_args(),
                commit_service=git_commit.GitCommitService(),
                push_service=FailingPushService(),
            )

        assert "push failed" in str(exc_info.value).lower()
        assert "no upstream configured" in str(exc_info.value)
        # Commit must remain.
        head = _run_git(patched_repo, "log", "-1", "--oneline", check=True).stdout.strip()
        assert "Add sample" in head

    def test_keyboard_interrupt_at_push_prompt_leaves_commit_intact(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        push_service = git_commit.NoopPushService()

        with patch(
            "toolsmith.ui.prompts.input", side_effect=["a", KeyboardInterrupt()]
        ):
            code = commit_writer.run(
                _make_args(),
                commit_service=git_commit.GitCommitService(),
                push_service=push_service,
            )

        assert code == 0
        assert len(push_service.calls) == 0
        head = _run_git(patched_repo, "log", "-1", "--oneline", check=True).stdout.strip()
        assert "Add sample" in head


class TestRealPush:
    def test_explicit_yes_pushes_to_local_bare_remote(
        self, monkeypatch, tmp_path, patched_repo, fake_llm_client
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        origin = tmp_path / "origin.git"
        origin.mkdir()
        _run_git(origin, "init", "--bare", "-q", check=True)
        _run_git(patched_repo, "remote", "add", "origin", str(origin), check=True)

        with patch("toolsmith.ui.prompts.input", side_effect=["a", "y"]):
            code = commit_writer.run(
                _make_args(),
                commit_service=git_commit.GitCommitService(),
                push_service=git_commit.GitPushService(),
            )

        assert code == 0
        pushed = _run_git(origin, "log", "--oneline", check=True).stdout.strip()
        assert "Add sample" in pushed
