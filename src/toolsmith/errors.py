"""toolsmith error taxonomy and exit-code mapping (Phase 2+)."""

from __future__ import annotations


class ToolsmithError(Exception):
    """Base class for all toolsmith errors."""

    exit_code: int = 1


class UsageError(ToolsmithError):
    """Invalid usage, environment, or configuration."""

    exit_code = 3


class DependencyError(ToolsmithError):
    """External dependency failure (git, LLM runtime, editor)."""

    exit_code = 4
