"""Commit and push creation (Phase 6 fake services).

This module defines the service boundary for git commit and push operations.
Phase 6 keeps the real implementation behind a fake/noop interface so the
interactive review/editor/dry-run flow can be tested without mutating any
repository.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable


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
