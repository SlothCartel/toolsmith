"""Unit tests for staged diff preparation and summary parsing."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

from toolsmith.errors import GitError, NoStagedChangesError
from toolsmith.git import diff


def test_parse_name_status_add_modify_delete():
    text = "A\tadded.txt\nM\tmodified.txt\nD\tdeleted.txt"
    entries = diff._parse_name_status(text)
    assert entries == [
        ("A", "added.txt", None),
        ("M", "modified.txt", None),
        ("D", "deleted.txt", None),
    ]


def test_parse_name_status_rename_and_copy():
    text = "R100\told.txt\tnew.txt\nC095\tsrc.txt\tdst.txt"
    entries = diff._parse_name_status(text)
    assert entries == [
        ("R", "new.txt", "old.txt"),
        ("C", "dst.txt", "src.txt"),
    ]


def test_parse_name_status_ignores_blank_lines():
    text = "\nA\tfile.txt\n\n"
    entries = diff._parse_name_status(text)
    assert entries == [("A", "file.txt", None)]


def test_parse_binary_paths_detects_binary_entries():
    text = "10\t5\ttext.txt\n-\t-\tbinary.bin\n"
    assert diff._parse_binary_paths(text) == {"binary.bin"}


def test_parse_binary_paths_detects_binary_renames():
    text = "-\t-\told.bin => new.bin\n"
    assert diff._parse_binary_paths(text) == {"old.bin", "new.bin"}


def test_parse_binary_paths_empty_for_all_text():
    text = "3\t2\ta.py\n0\t10\tb.py\n"
    assert diff._parse_binary_paths(text) == set()


def test_apply_truncation_below_limit_is_unmodified():
    diff_text = "small diff"
    bounded, truncated = diff._apply_truncation(diff_text, 100)
    assert bounded == diff_text
    assert truncated is False


def test_apply_truncation_at_limit_is_unmodified():
    diff_text = "x" * 50
    bounded, truncated = diff._apply_truncation(diff_text, 50)
    assert bounded == diff_text
    assert truncated is False


def test_apply_truncation_above_limit_adds_marker():
    diff_text = "x" * 100
    bounded, truncated = diff._apply_truncation(diff_text, 50)
    assert truncated is True
    assert bounded.startswith("x" * 50)
    assert "truncated" in bounded
    assert bounded.endswith("]\n")


def test_apply_truncation_is_deterministic():
    diff_text = "x" * 200
    a, _ = diff._apply_truncation(diff_text, 75)
    b, _ = diff._apply_truncation(diff_text, 75)
    assert a == b


@patch("toolsmith.git.diff._run_git")
def test_prepare_staged_diff_returns_prepared_diff(mock_run_git, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mock_run_git.side_effect = [
        _FakeResult("A\tadded.txt\nM\tmodified.txt"),
        _FakeResult("10\t0\tadded.txt\n5\t2\tmodified.txt"),
        _FakeResult("diff text here"),
    ]

    prepared = diff.prepare_staged_diff(repo, max_diff_chars=1000)
    assert prepared.repository_root == repo
    assert prepared.max_diff_chars == 1000
    assert prepared.truncated is False
    assert prepared.original_diff_chars == len("diff text here")
    assert prepared.diff == "diff text here"
    summary = {entry.path: entry for entry in prepared.summary}
    assert summary["added.txt"].status == "A"
    assert summary["added.txt"].is_binary is False
    assert summary["modified.txt"].status == "M"


@patch("toolsmith.git.diff._run_git")
def test_prepare_staged_diff_marks_binary_files(mock_run_git, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mock_run_git.side_effect = [
        _FakeResult("A\timage.png\nR100\told.txt\tnew.txt"),
        _FakeResult("-\t-\timage.png\n-\t-\told.txt => new.txt"),
        _FakeResult("binary marker here"),
    ]

    prepared = diff.prepare_staged_diff(repo, max_diff_chars=1000)
    by_path = {entry.path: entry for entry in prepared.summary}
    assert by_path["image.png"].is_binary is True
    assert by_path["new.txt"].is_binary is True


@patch("toolsmith.git.diff._run_git")
def test_prepare_staged_diff_raises_when_no_staged_changes(mock_run_git, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mock_run_git.side_effect = [
        _FakeResult(""),
        _FakeResult(""),
        _FakeResult(""),
    ]

    with pytest.raises(NoStagedChangesError) as exc_info:
        diff.prepare_staged_diff(repo, max_diff_chars=1000)
    assert "staged" in str(exc_info.value).lower()


@patch("toolsmith.git.diff._run_git")
def test_prepare_staged_diff_propagates_git_errors(mock_run_git, tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    mock_run_git.side_effect = GitError("git failed")

    with pytest.raises(GitError, match="git failed"):
        diff.prepare_staged_diff(repo, max_diff_chars=1000)


def test_prepare_staged_diff_rejects_non_positive_limit(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError):
        diff.prepare_staged_diff(repo, max_diff_chars=0)


class _FakeResult:
    """Minimal stand-in for subprocess.CompletedProcess[str]."""

    def __init__(self, stdout: str, returncode: int = 0, stderr: str = ""):
        self.stdout = stdout
        self.returncode = returncode
        self.stderr = stderr


@patch("toolsmith.git.diff._run_git")
def test_prepare_staged_diff_uses_cached_args(mock_run_git, tmp_path):
    """The summary and diff must be collected with --cached arguments only."""
    repo = tmp_path / "repo"
    repo.mkdir()
    mock_run_git.side_effect = [
        _FakeResult("A\tfile.txt"),
        _FakeResult("10\t0\tfile.txt"),
        _FakeResult("diff"),
    ]

    diff.prepare_staged_diff(repo, max_diff_chars=100)

    calls = [c.args for c in mock_run_git.call_args_list]
    assert calls == [
        (repo, "diff", "--cached", "--name-status"),
        (repo, "diff", "--cached", "--numstat"),
        (repo, "diff", "--cached"),
    ]
