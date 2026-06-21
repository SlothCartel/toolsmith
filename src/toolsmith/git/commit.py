"""Commit and push creation.

This module defines the service boundary for git commit and push operations.
Phase 6 kept the real implementation behind a fake/noop interface so the
interactive review/editor/dry-run flow could be tested without mutating any
repository. Phase 7 adds the real :class:`GitCommitService` and
:class:`GitPushService`, which use subprocess argument arrays and secure
temporary commit-message files.
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from toolsmith.git.repository import _run_git


@dataclass(frozen=True)
class CommitResult:
    """Result of creating a commit."""

    success: bool
    message: str = ""


@dataclass(frozen=True)
class PushResult:
    """Result of pushing a branch."""

    success: bool
    message: str = ""


@runtime_checkable
class CommitService(Protocol):
    """Boundary for creating a git commit from an accepted message."""

    def create_commit(
        self,
        *,
        repository_root: Path,
        message: str,
    ) -> CommitResult:
        """Create a commit in *repository_root* with *message*.

        Implementations must preserve normal git hooks and signing behavior.
        """
        ...


@runtime_checkable
class PushService(Protocol):
    """Boundary for pushing a branch."""

    def push(self, *, repository_root: Path) -> PushResult:
        """Push the current branch in *repository_root* using ordinary git push."""
        ...


class NoopCommitService:
    """Fake commit service that records calls without mutating git."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def create_commit(
        self,
        *,
        repository_root: Path,
        message: str,
    ) -> CommitResult:
        self.calls.append({"repository_root": repository_root, "message": message})
        return CommitResult(success=True, message="Commit created (noop).")


class NoopPushService:
    """Fake push service that records calls without mutating git."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def push(self, *, repository_root: Path) -> PushResult:
        self.calls.append({"repository_root": repository_root})
        return PushResult(success=True, message="Push completed (noop).")


class GitCommitService:
    """Real commit service using ``git commit -F <message-file>``.

    The message is written to a secure temporary file and the file is removed
    in a ``finally``-style path on both success and failure. No hook-bypass
    or signing-management flags are passed, so normal git hooks and the
    user's existing signing configuration are preserved.
    """

    def create_commit(
        self,
        *,
        repository_root: Path,
        message: str,
    ) -> CommitResult:
        fd, path = tempfile.mkstemp(prefix="toolsmith-commit-message-", suffix=".txt")
        try:
            os.close(fd)
            with open(path, "w", encoding="utf-8") as handle:
                handle.write(message)

            result = _run_git(
                repository_root, "commit", "-F", str(path), check=False
            )
            if result.returncode != 0:
                stderr = result.stderr.strip()
                return CommitResult(
                    success=False,
                    message=stderr or f"git commit exited with status {result.returncode}",
                )
            return CommitResult(
                success=True,
                message=result.stdout.strip() or "Commit created.",
            )
        finally:
            try:
                os.unlink(path)
            except OSError:
                pass


class GitPushService:
    """Real push service using ordinary ``git push``.

    No ``--force`` or ``--force-with-lease`` flag is ever passed.
    """

    def push(self, *, repository_root: Path) -> PushResult:
        result = _run_git(repository_root, "push", check=False)
        if result.returncode != 0:
            stderr = result.stderr.strip()
            return PushResult(
                success=False,
                message=stderr or f"git push exited with status {result.returncode}",
            )
        return PushResult(
            success=True,
            message=result.stdout.strip() or "Push completed.",
        )
