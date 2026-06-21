"""Unit tests for Commit Writer orchestration (Phases 5 and 6)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from toolsmith.commands import commit_writer
from toolsmith.errors import CancelError, DependencyError, EmptyCommitMessageError, GitError, NoRepositoryError, NoStagedChangesError, UsageError
from toolsmith.git import commit as git_commit
from toolsmith.git.diff import PreparedDiff, StatusEntry
from toolsmith.llm.base import LLMResponse
from toolsmith.prompts import commit_writer as commit_prompts

from .fake_llm import FakeLLMClient


def _make_args(
    *, no_push: bool = False, dry_run: bool = False, model: str | None = None
) -> argparse.Namespace:
    return argparse.Namespace(no_push=no_push, dry_run=dry_run, model=model)


def _prepared(diff: str = "@@ -1 +1 @@\n-old\n+new") -> PreparedDiff:
    return PreparedDiff(
        repository_root=Path("/repo"),
        summary=(StatusEntry(status="M", path="file.py"),),
        diff=diff,
        truncated=False,
        original_diff_chars=len(diff),
        max_diff_chars=12000,
    )


@pytest.fixture
def fake_llm_client() -> FakeLLMClient:
    return FakeLLMClient(
        response=LLMResponse(
            text="Fix staged diff detection\n\nUse the cached diff.",
            success=True,
        )
    )


class _RecordingCommitService(git_commit.NoopCommitService):
    def create_commit(self, *, repository_root: Path, message: str) -> git_commit.CommitResult:
        super().create_commit(repository_root=repository_root, message=message)
        return git_commit.CommitResult(success=True)


class _RecordingPushService(git_commit.NoopPushService):
    def push(self, *, repository_root: Path) -> git_commit.PushResult:
        super().push(repository_root=repository_root)
        return git_commit.PushResult(success=True)


@pytest.fixture
def patched_repo(monkeypatch):
    """Patch git discovery to a synthetic prepared diff."""
    prepared = _prepared()
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_repository.find_repository_root",
        lambda: prepared.repository_root,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_diff.prepare_staged_diff",
        lambda root, max_chars: prepared,
    )
    return prepared


def test_orchestration_passes_exact_prompt_and_settings(
    monkeypatch, tmp_path, fake_llm_client, patched_repo
):
    monkeypatch.setenv("HOME", str(tmp_path))
    expected_prompt = commit_prompts.build_commit_prompt(patched_repo)
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: fake_llm_client,
    )

    code = commit_writer.run(_make_args(dry_run=True))

    assert code == 0
    assert len(fake_llm_client.calls) == 1
    request = fake_llm_client.calls[0]
    assert request.prompt == expected_prompt
    assert request.model == "qwen2.5-coder:7b"
    assert request.temperature == 0.2
    assert request.max_tokens == 512
    assert request.timeout_seconds == 20.0


def test_orchestration_prints_cleaned_message(
    monkeypatch, tmp_path, fake_llm_client, patched_repo, capsys
):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: fake_llm_client,
    )

    code = commit_writer.run(_make_args(dry_run=True))
    captured = capsys.readouterr()

    assert code == 0
    assert "Fix staged diff detection" in captured.out
    assert "Use the cached diff" in captured.out


def test_orchestration_propagates_llm_failure(monkeypatch, tmp_path, patched_repo):
    monkeypatch.setenv("HOME", str(tmp_path))
    client = FakeLLMClient(
        response=LLMResponse(
            text="", success=False, error="Local LLM runtime is unavailable."
        )
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: client,
    )

    with pytest.raises(DependencyError) as exc_info:
        commit_writer.run(_make_args())
    assert "unavailable" in str(exc_info.value)


def test_orchestration_rejects_empty_cleaned_message(monkeypatch, tmp_path, patched_repo):
    monkeypatch.setenv("HOME", str(tmp_path))
    client = FakeLLMClient(response=LLMResponse(text="```\n```", success=True))
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: client,
    )

    with pytest.raises(EmptyCommitMessageError):
        commit_writer.run(_make_args())


def test_orchestration_warns_on_long_subject(
    monkeypatch, tmp_path, patched_repo, capsys
):
    monkeypatch.setenv("HOME", str(tmp_path))
    long_subject = "x" * 80
    client = FakeLLMClient(response=LLMResponse(text=long_subject, success=True))
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: client,
    )

    code = commit_writer.run(_make_args(dry_run=True))
    captured = capsys.readouterr()

    assert code == 0
    assert long_subject in captured.out
    assert "72" in captured.err


class TestInteractiveReview:
    def test_accept_creates_commit_and_prompts_push_yes(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with patch("toolsmith.ui.prompts.input", side_effect=["a", "y"]):
            code = commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert code == 0
        assert len(commit_service.calls) == 1
        assert "Fix staged diff detection" in commit_service.calls[0]["message"]
        assert len(push_service.calls) == 1

    def test_accept_no_push_when_prompt_push_false(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with patch("toolsmith.ui.prompts.input", side_effect=["a"]):
            code = commit_writer.run(
                _make_args(no_push=True),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert code == 0
        assert len(commit_service.calls) == 1
        assert len(push_service.calls) == 0

    def test_push_prompt_default_no(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with patch("toolsmith.ui.prompts.input", side_effect=["a", ""]):
            code = commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert code == 0
        assert len(commit_service.calls) == 1
        assert len(push_service.calls) == 0

    def test_reject_raises_cancel_and_makes_no_calls(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with patch("toolsmith.ui.prompts.input", side_effect=["r"]), pytest.raises(
            CancelError
        ) as exc_info:
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert "rejected" in str(exc_info.value).lower()
        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    def test_keyboard_interrupt_at_review_makes_no_calls(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with patch(
            "toolsmith.ui.prompts.input", side_effect=KeyboardInterrupt()
        ), pytest.raises(KeyboardInterrupt):
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    def test_invalid_input_reprompts_then_accepts(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with patch(
            "toolsmith.ui.prompts.input", side_effect=["nope", "", "a", ""]
        ):
            code = commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert code == 0
        assert len(commit_service.calls) == 1
        assert len(push_service.calls) == 0  # blank at push prompt means no


class TestEditFlow:
    def test_edit_message_is_validated_and_committed(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        edited = "Edited commit subject\n\nEdited body."

        def fake_edit(message: str) -> str:
            assert "Fix staged diff detection" in message
            return edited

        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.editor.edit_message", fake_edit
        )

        with patch("toolsmith.ui.prompts.input", side_effect=["e", "a", ""]):
            code = commit_writer.run(
                _make_args(no_push=True),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert code == 0
        assert len(commit_service.calls) == 1
        assert commit_service.calls[0]["message"] == edited
        assert len(push_service.calls) == 0

    def test_empty_edited_message_cannot_call_commit(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.editor.edit_message",
            lambda message: "   \n\n   ",
        )

        with patch("toolsmith.ui.prompts.input", side_effect=["e"]), pytest.raises(
            EmptyCommitMessageError
        ):
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    def test_editor_failure_cannot_call_commit(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        def failing_edit(message: str) -> str:
            raise DependencyError("Editor unavailable.")

        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.editor.edit_message", failing_edit
        )

        with patch("toolsmith.ui.prompts.input", side_effect=["e"]), pytest.raises(
            DependencyError
        ):
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0


class TestDryRun:
    def test_dry_run_generates_displays_and_exits_without_approval(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo, capsys
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        code = commit_writer.run(
            _make_args(dry_run=True, no_push=True),
            commit_service=commit_service,
            push_service=push_service,
        )
        captured = capsys.readouterr()

        assert code == 0
        assert "Fix staged diff detection" in captured.out
        assert "Dry run" in captured.out
        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    def test_dry_run_does_not_prompt_for_approval_or_push(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )
        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        # If input were called, this side_effect would raise and fail the test.
        with patch("toolsmith.ui.prompts.input", side_effect=Exception("prompted")):
            code = commit_writer.run(
                _make_args(dry_run=True),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert code == 0
        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0



class TestErrorPaths:
    """Safety/orchestration tests proving early errors skip LLM and services."""

    def test_invalid_config_raises_before_git_and_llm(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("HOME", str(tmp_path))

        def raise_usage(*args, **kwargs):
            raise UsageError("bad config")

        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.config.build_config", raise_usage
        )
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.git_repository.find_repository_root",
            lambda: (_ for _ in ()).throw(AssertionError("git should not be called")),
        )

        client_spy: list[object] = []
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: client_spy.append(provider) or (_ for _ in ()).throw(
                AssertionError("LLM client should not be constructed")
            ),
        )

        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with pytest.raises(UsageError):
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert client_spy == []
        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    def test_outside_repository_raises_before_llm_and_services(
        self, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.git_repository.find_repository_root",
            lambda: (_ for _ in ()).throw(NoRepositoryError("not a repo")),
        )

        client_spy: list[object] = []
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: client_spy.append(provider) or (_ for _ in ()).throw(
                AssertionError("LLM client should not be constructed")
            ),
        )

        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with pytest.raises(NoRepositoryError):
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert client_spy == []
        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    def test_no_staged_changes_raises_before_llm_and_services(
        self, monkeypatch, tmp_path, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.git_diff.prepare_staged_diff",
            lambda root, max_chars: (_ for _ in ()).throw(
                NoStagedChangesError("no staged changes")
            ),
        )

        client_spy: list[object] = []
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: client_spy.append(provider) or (_ for _ in ()).throw(
                AssertionError("LLM client should not be constructed")
            ),
        )

        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with pytest.raises(NoStagedChangesError):
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert client_spy == []
        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    def test_diff_failure_raises_before_llm_and_services(
        self, monkeypatch, tmp_path, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.git_diff.prepare_staged_diff",
            lambda root, max_chars: (_ for _ in ()).throw(GitError("diff failed")),
        )

        client_spy: list[object] = []
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: client_spy.append(provider) or (_ for _ in ()).throw(
                AssertionError("LLM client should not be constructed")
            ),
        )

        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with pytest.raises(GitError):
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert client_spy == []
        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    @pytest.mark.parametrize(
        "response",
        [
            LLMResponse(
                text="",
                success=False,
                error="Local LLM runtime is unavailable.",
            ),
            LLMResponse(text="", success=False, error="Local LLM request timed out."),
            LLMResponse(
                text="",
                success=False,
                error="LLM returned malformed response: not json",
            ),
            LLMResponse(text="", success=False, error="LLM returned empty output."),
        ],
    )
    def test_llm_failure_variants_block_commit_and_push(
        self, monkeypatch, tmp_path, patched_repo, response
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        client = FakeLLMClient(response=response)
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: client,
        )

        commit_service = _RecordingCommitService()
        push_service = _RecordingPushService()

        with pytest.raises(DependencyError):
            commit_writer.run(
                _make_args(),
                commit_service=commit_service,
                push_service=push_service,
            )

        assert len(client.calls) == 1
        assert len(commit_service.calls) == 0
        assert len(push_service.calls) == 0

    def test_commit_service_failure_raises_git_error_and_skips_push(
        self, monkeypatch, tmp_path, fake_llm_client, patched_repo
    ):
        monkeypatch.setenv("HOME", str(tmp_path))
        monkeypatch.setattr(
            "toolsmith.commands.commit_writer.llm.create_client",
            lambda provider: fake_llm_client,
        )

        class FailingCommitService(git_commit.CommitService):
            def create_commit(
                self, *, repository_root: Path, message: str
            ) -> git_commit.CommitResult:
                return git_commit.CommitResult(
                    success=False, message="commit-msg hook rejected"
                )

        push_service = _RecordingPushService()

        with patch("toolsmith.ui.prompts.input", side_effect=["a"]), pytest.raises(
            GitError
        ) as exc_info:
            commit_writer.run(
                _make_args(),
                commit_service=FailingCommitService(),
                push_service=push_service,
            )

        assert "commit-msg hook rejected" in str(exc_info.value)
        assert len(push_service.calls) == 0
