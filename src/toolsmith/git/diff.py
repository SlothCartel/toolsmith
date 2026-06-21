"""Staged diff and file-summary collection (Phase 3)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from toolsmith.errors import NoStagedChangesError
from toolsmith.git.repository import _run_git


@dataclass(frozen=True)
class StatusEntry:
    """A single staged file summary entry."""

    status: str
    path: str
    old_path: str | None = None
    is_binary: bool = False


@dataclass(frozen=True)
class PreparedDiff:
    """Bounded staged diff result ready for prompt construction."""

    repository_root: Path
    summary: tuple[StatusEntry, ...]
    diff: str
    truncated: bool
    original_diff_chars: int
    max_diff_chars: int


_TRUNCATION_MARKER = "\n\n[toolsmith: staged diff truncated at max_diff_chars limit]\n"


def _status_letter(status_field: str) -> str:
    """Return the alphabetic status letter, ignoring rename/copy scores."""
    if not status_field:
        return "?"
    return status_field[0].upper()


def _parse_name_status(text: str) -> list[tuple[str, str, str | None]]:
    """Parse `git diff --cached --name-status` output.

    Returns a list of (status_letter, path, old_path_or_none).
    """
    entries: list[tuple[str, str, str | None]] = []
    for line in text.splitlines():
        line = line.rstrip("\r")
        if not line:
            continue
        parts = line.split("\t")
        status = _status_letter(parts[0])
        if status in {"R", "C"}:
            if len(parts) < 3:
                continue
            old_path = parts[1]
            new_path = parts[2]
            entries.append((status, new_path, old_path))
        else:
            if len(parts) < 2:
                continue
            entries.append((status, parts[1], None))
    return entries


def _parse_binary_paths(numstat_text: str) -> set[str]:
    """Identify binary files from `git diff --cached --numstat` output.

    Binary entries are represented as ``-\t-\tpath``. Rename lines use the
    format ``old_path => new_path``; both paths are recorded as binary so
    that the matching summary entry can be flagged correctly.
    """
    binary_paths: set[str] = set()
    for line in numstat_text.splitlines():
        line = line.rstrip("\r")
        if not line:
            continue
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        if parts[0] == "-" and parts[1] == "-":
            path_field = parts[2]
            if " => " in path_field:
                old_path, _, new_path = path_field.partition(" => ")
                binary_paths.add(old_path)
                binary_paths.add(new_path)
            else:
                binary_paths.add(path_field)
    return binary_paths


def _collect_summary(repo_root: Path) -> tuple[StatusEntry, ...]:
    """Collect the staged name-status summary and mark binary files."""
    name_status = _run_git(
        repo_root, "diff", "--cached", "--name-status", check=True
    ).stdout
    numstat = _run_git(repo_root, "diff", "--cached", "--numstat", check=True).stdout

    binary_paths = _parse_binary_paths(numstat)
    raw_entries = _parse_name_status(name_status)

    return tuple(
        StatusEntry(
            status=status,
            path=path,
            old_path=old_path,
            is_binary=path in binary_paths or (old_path is not None and old_path in binary_paths),
        )
        for status, path, old_path in raw_entries
    )


def _collect_diff(repo_root: Path) -> str:
    """Collect the textual staged diff from `git diff --cached`."""
    return _run_git(repo_root, "diff", "--cached", check=True).stdout


def _apply_truncation(diff_text: str, max_diff_chars: int) -> tuple[str, bool]:
    """Return the diff bounded to *max_diff_chars* with an explicit marker."""
    if len(diff_text) <= max_diff_chars:
        return diff_text, False
    return diff_text[:max_diff_chars] + _TRUNCATION_MARKER, True


def prepare_staged_diff(repo_root: Path | str, max_diff_chars: int) -> PreparedDiff:
    """Prepare a bounded, read-only summary of the staged git index.

    Only ``--cached`` data is used. Unstaged changes are never included. Binary
    files are identified through git metadata (``--numstat``) and working-tree
    contents are never opened.

    Raises:
        NoStagedChangesError: When the staged index is empty.
        GitError: When a git subprocess command fails.
    """
    root = Path(repo_root)
    if max_diff_chars <= 0:
        raise ValueError("max_diff_chars must be positive")

    summary = _collect_summary(root)
    if not summary:
        raise NoStagedChangesError(
            "No staged changes found. Stage changes with `git add` before running `toolsmith cw`."
        )

    diff_text = _collect_diff(root)
    bounded_diff, truncated = _apply_truncation(diff_text, max_diff_chars)

    return PreparedDiff(
        repository_root=root,
        summary=summary,
        diff=bounded_diff,
        truncated=truncated,
        original_diff_chars=len(diff_text),
        max_diff_chars=max_diff_chars,
    )
