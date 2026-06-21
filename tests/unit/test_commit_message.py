"""Tests for commit-message cleanup and validation."""

from __future__ import annotations

import pytest

from toolsmith.errors import EmptyCommitMessageError
from toolsmith.prompts.commit_writer import clean_commit_message, validate_commit_message


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("Fix staged diff detection\n", "Fix staged diff detection"),
        (
            "  \nFix staged diff detection\n  \n",
            "Fix staged diff detection",
        ),
        (
            "\n\n\nFix detection\n\n\n",
            "Fix detection",
        ),
        (
            '```\nFix detection\n```\n',
            "Fix detection",
        ),
        (
            '```text\nFix detection\n```',
            "Fix detection",
        ),
        (
            '"Fix detection"',
            "Fix detection",
        ),
        (
            "'Fix detection'",
            "Fix detection",
        ),
        (
            "Commit message: Fix detection",
            "Fix detection",
        ),
        (
            "Commit message: \"Fix detection\"",
            "Fix detection",
        ),
        (
            "Suggested commit message:\n\nFix detection",
            "Fix detection",
        ),
        (
            "```\nCommit message: Fix detection\n```",
            "Fix detection",
        ),
        (
            "Fix detection\n\n\n\nUse the cached diff.\n",
            "Fix detection\n\nUse the cached diff.",
        ),
        (
            "\n\n```\n\nFix detection\n\n```\n\n",
            "Fix detection",
        ),
    ],
)
def test_clean_commit_message(raw, expected):
    assert clean_commit_message(raw) == expected


def test_clean_commit_message_is_idempotent():
    cleaned = clean_commit_message(
        "```\nCommit message: \"Fix detection\"\n```\n"
    )
    assert clean_commit_message(cleaned) == cleaned


def test_clean_preserves_substantive_quotes_inside_body():
    raw = 'Fix detection\n\nUse "cached" diff.'
    assert clean_commit_message(raw) == raw


def test_clean_preserves_multi_paragraph_body():
    raw = "Fix detection\n\nFirst paragraph.\n\nSecond paragraph."
    assert clean_commit_message(raw) == raw


def test_validate_rejects_empty_message():
    with pytest.raises(EmptyCommitMessageError):
        validate_commit_message("")


def test_validate_rejects_whitespace_only_message():
    with pytest.raises(EmptyCommitMessageError):
        validate_commit_message("   \n\n   ")


def test_validate_extracts_subject_and_empty_body():
    result = validate_commit_message("Fix detection")
    assert result.subject == "Fix detection"
    assert result.body == ""
    assert result.warnings == ()


def test_validate_extracts_subject_and_body():
    result = validate_commit_message(
        "Fix detection\n\nUse the cached diff.\n"
    )
    assert result.subject == "Fix detection"
    assert result.body == "Use the cached diff."
    assert result.warnings == ()


def test_validate_subject_at_72_chars_has_no_warning():
    subject = "x" * 72
    result = validate_commit_message(subject)
    assert result.subject == subject
    assert result.warnings == ()


def test_validate_subject_over_72_chars_emits_warning():
    subject = "x" * 73
    result = validate_commit_message(subject)
    assert result.subject == subject
    assert len(result.warnings) == 1
    assert "72" in result.warnings[0]


def test_validate_long_subject_warning_does_not_block_acceptance():
    result = validate_commit_message("x" * 80)
    assert result.subject == "x" * 80
    assert result.warnings
