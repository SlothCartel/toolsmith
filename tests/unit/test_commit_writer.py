"""Unit tests for Commit Writer orchestration (Phase 5)."""

from __future__ import annotations

import argparse
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from toolsmith.commands import commit_writer
from toolsmith.errors import DependencyError, EmptyCommitMessageError
from toolsmith.git.diff import PreparedDiff, StatusEntry
from toolsmith.llm.base import LLMResponse
from toolsmith.prompts import commit_writer as commit_prompts

from .fake_llm import FakeLLMClient


def _make_args(*, no_push: bool = False, dry_run: bool = False, model: str | None = None) -> argparse.Namespace:
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


def test_orchestration_passes_exact_prompt_and_settings(
    monkeypatch, tmp_path, fake_llm_client
):
    monkeypatch.setenv("HOME", str(tmp_path))
    prepared = _prepared()
    expected_prompt = commit_prompts.build_commit_prompt(prepared)

    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_repository.find_repository_root",
        lambda: prepared.repository_root,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_diff.prepare_staged_diff",
        lambda root, max_chars: prepared,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: fake_llm_client,
    )

    code = commit_writer.run(_make_args())

    assert code == 0
    assert len(fake_llm_client.calls) == 1
    request = fake_llm_client.calls[0]
    assert request.prompt == expected_prompt
    assert request.model == "qwen2.5-coder:7b"
    assert request.temperature == 0.2
    assert request.max_tokens == 512
    assert request.timeout_seconds == 20.0


def test_orchestration_prints_cleaned_message(
    monkeypatch, tmp_path, fake_llm_client, capsys
):
    monkeypatch.setenv("HOME", str(tmp_path))
    prepared = _prepared()

    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_repository.find_repository_root",
        lambda: prepared.repository_root,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_diff.prepare_staged_diff",
        lambda root, max_chars: prepared,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: fake_llm_client,
    )

    code = commit_writer.run(_make_args())
    captured = capsys.readouterr()

    assert code == 0
    assert "Fix staged diff detection" in captured.out
    assert "Use the cached diff" in captured.out


def test_orchestration_propagates_llm_failure(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    client = FakeLLMClient(
        response=LLMResponse(
            text="", success=False, error="Local LLM runtime is unavailable."
        )
    )
    prepared = _prepared()

    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_repository.find_repository_root",
        lambda: prepared.repository_root,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_diff.prepare_staged_diff",
        lambda root, max_chars: prepared,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: client,
    )

    with pytest.raises(DependencyError) as exc_info:
        commit_writer.run(_make_args())
    assert "unavailable" in str(exc_info.value)


def test_orchestration_rejects_empty_cleaned_message(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    client = FakeLLMClient(response=LLMResponse(text="```\n```", success=True))
    prepared = _prepared()

    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_repository.find_repository_root",
        lambda: prepared.repository_root,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_diff.prepare_staged_diff",
        lambda root, max_chars: prepared,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: client,
    )

    with pytest.raises(EmptyCommitMessageError):
        commit_writer.run(_make_args())


def test_orchestration_warns_on_long_subject(monkeypatch, tmp_path, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    long_subject = "x" * 80
    client = FakeLLMClient(response=LLMResponse(text=long_subject, success=True))
    prepared = _prepared()

    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_repository.find_repository_root",
        lambda: prepared.repository_root,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.git_diff.prepare_staged_diff",
        lambda root, max_chars: prepared,
    )
    monkeypatch.setattr(
        "toolsmith.commands.commit_writer.llm.create_client",
        lambda provider: client,
    )

    code = commit_writer.run(_make_args())
    captured = capsys.readouterr()

    assert code == 0
    assert long_subject in captured.out
    assert "72" in captured.err
