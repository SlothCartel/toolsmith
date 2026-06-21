"""Tests for Commit Writer prompt construction."""

from __future__ import annotations

from pathlib import Path

import pytest

from toolsmith.git.diff import PreparedDiff, StatusEntry
from toolsmith.prompts.commit_writer import build_commit_prompt


def _prepared(
    summary: tuple[StatusEntry, ...],
    diff: str,
    truncated: bool = False,
    max_diff_chars: int = 12000,
) -> PreparedDiff:
    return PreparedDiff(
        repository_root=Path("/repo"),
        summary=summary,
        diff=diff,
        truncated=truncated,
        original_diff_chars=len(diff),
        max_diff_chars=max_diff_chars,
    )


def _entry(status: str, path: str, old_path: str | None = None, is_binary: bool = False) -> StatusEntry:
    return StatusEntry(status=status, path=path, old_path=old_path, is_binary=is_binary)


@pytest.mark.parametrize(
    "name,summary,diff",
    [
        ("simple", (_entry("M", "src/main.py"),), "@@ -1 +1 @@\n-old\n+new"),
        (
            "multi_file",
            (
                _entry("M", "src/main.py"),
                _entry("A", "tests/test_main.py"),
                _entry("M", "README.md"),
            ),
            "multi-file diff",
        ),
        (
            "documentation",
            (_entry("M", "README.md"), _entry("A", "docs/usage.md")),
            "doc diff",
        ),
        (
            "rename",
            (_entry("R", "new_name.py", old_path="old_name.py"),),
            "rename diff",
        ),
        (
            "delete",
            (_entry("D", "legacy.py"),),
            "delete diff",
        ),
        (
            "binary",
            (_entry("A", "image.png", is_binary=True),),
            "",
        ),
        (
            "noisy",
            (
                _entry("M", "package-lock.json"),
                _entry("M", "dist/bundle.min.js"),
                _entry("M", "src/main.py"),
            ),
            "noisy diff",
        ),
    ],
)
def test_prompt_includes_summary_and_diff(name, summary, diff):
    prepared = _prepared(summary, diff)
    prompt = build_commit_prompt(prepared)

    assert "Staged file summary:" in prompt
    assert "Staged diff:" in prompt
    for entry in summary:
        assert entry.path in prompt
    if diff:
        assert diff in prompt


def test_prompt_includes_required_constraints():
    prepared = _prepared((_entry("M", "file.py"),), "diff")
    prompt = build_commit_prompt(prepared)

    assert "imperative" in prompt.lower()
    assert "ticket numbers" in prompt.lower()
    assert "authors" in prompt.lower()
    assert "reviewers" in prompt.lower()
    assert "deployment notes" in prompt.lower()
    assert "breaking-change" in prompt.lower() or "breaking change" in prompt.lower()
    assert "security claims" in prompt.lower()
    assert "test claims" in prompt.lower()
    assert "markdown" in prompt.lower()
    assert "code fences" in prompt.lower()
    assert "preamble" in prompt.lower()
    assert "lockfiles" in prompt.lower()
    assert "generated files" in prompt.lower()
    assert "minified" in prompt.lower()


def test_prompt_includes_output_shape():
    prepared = _prepared((_entry("M", "file.py"),), "diff")
    prompt = build_commit_prompt(prepared)

    assert "Output shape:" in prompt
    assert "<subject>" in prompt
    assert "<optional body>" in prompt


def test_prompt_includes_truncation_metadata_when_truncated():
    diff = "x" * 50 + "[truncated]\n"
    prepared = _prepared(
        (_entry("M", "file.py"),),
        diff,
        truncated=True,
        max_diff_chars=50,
    )
    prompt = build_commit_prompt(prepared)

    assert diff in prompt
    assert "truncated" in prompt.lower()


def test_prompt_does_not_claim_truncation_when_not_truncated():
    prepared = _prepared((_entry("M", "file.py"),), "short diff")
    prompt = build_commit_prompt(prepared)

    assert "short diff" in prompt
    # The word "truncated" should not appear when the diff is not truncated.
    assert "truncated" not in prompt.lower()


def test_prompt_is_deterministic():
    prepared = _prepared(
        (
            _entry("A", "new.py"),
            _entry("M", "README.md"),
        ),
        "diff text",
    )
    assert build_commit_prompt(prepared) == build_commit_prompt(prepared)


def test_prompt_summary_renders_rename_and_binary():
    prepared = _prepared(
        (
            _entry("R", "new.py", old_path="old.py"),
            _entry("A", "image.png", is_binary=True),
            _entry("D", "gone.py"),
        ),
        "diff",
    )
    prompt = build_commit_prompt(prepared)

    assert "R old.py -> new.py" in prompt
    assert "A image.png (binary)" in prompt
    assert "D gone.py" in prompt


def test_prompt_summary_uses_only_staged_data():
    prepared = _prepared(
        (_entry("M", "staged.py"),),
        "staged diff only",
    )
    prompt = build_commit_prompt(prepared)

    assert "staged.py" in prompt
    assert "staged diff only" in prompt
    assert "unstaged" not in prompt.lower()
    assert "history" not in prompt.lower()



def test_prompt_size_respects_configured_diff_limit():
    """Prompt length stays bounded by the configured diff limit plus instructions.

    This is a non-flaky structural measurement, not a hardware-dependent timing
    assertion. The fixed instruction/summary overhead is expected to be small.
    """
    max_diff_chars = 500
    oversized_diff = "x" * 5000
    prepared = _prepared(
        (
            _entry("M", "src/main.py"),
            _entry("A", "tests/test_main.py"),
        ),
        oversized_diff,
        truncated=False,
        max_diff_chars=max_diff_chars,
    )
    # The diff module would have truncated; simulate by truncating manually.
    from toolsmith.git import diff as git_diff
    bounded, truncated = git_diff._apply_truncation(oversized_diff, max_diff_chars)
    prepared_truncated = _prepared(
        (
            _entry("M", "src/main.py"),
            _entry("A", "tests/test_main.py"),
        ),
        bounded,
        truncated=True,
        max_diff_chars=max_diff_chars,
    )
    prompt = build_commit_prompt(prepared_truncated)

    # Fixed overhead covers instructions, summary lines, and truncation marker.
    overhead = 1200
    assert len(prompt) <= max_diff_chars + overhead
    assert "truncated" in prompt.lower()
