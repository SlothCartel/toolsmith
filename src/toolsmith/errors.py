"""toolsmith error taxonomy and exit-code mapping."""

from __future__ import annotations


class ToolsmithError(Exception):
    """Base class for all toolsmith errors."""

    exit_code: int = 1


class CancelError(ToolsmithError):
    """User rejected or cancelled the operation."""

    exit_code = 2


class UsageError(ToolsmithError):
    """Invalid usage, environment, or configuration."""

    exit_code = 3


class DependencyError(ToolsmithError):
    """External dependency failure (git, LLM runtime, editor)."""

    exit_code = 4


class NoRepositoryError(UsageError):
    """The current directory is not inside a git repository."""


class NoStagedChangesError(UsageError):
    """No staged changes are present in the git index."""


class GitError(DependencyError):
    """A git subprocess command failed or produced an unexpected result."""


class EmptyCommitMessageError(DependencyError):
    """The LLM produced no usable commit message after cleanup."""


def render_message(exc: BaseException) -> str:
    """Return a concise, user-facing message for an exception."""
    return str(exc) if str(exc) else type(exc).__name__
