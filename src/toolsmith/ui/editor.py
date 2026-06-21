"""External editor invocation (Phase 6)."""

from __future__ import annotations

import os
import shutil
import subprocess
import tempfile

from toolsmith.errors import CancelError, DependencyError


# Phase 6 fallback. If $VISUAL and $EDITOR are unset and `vi` is on PATH,
# use it; otherwise fail with a clear message.
_FALLBACK_EDITOR = "vi"


def resolve_editor() -> str:
    """Resolve the external editor command.

    Resolution order:
      1. $VISUAL
      2. $EDITOR
      3. Documented executable fallback ``vi`` if present on PATH.

    Returns the executable path/name. Raises :class:`DependencyError` if no
    editor can be found.
    """
    editor = os.environ.get("VISUAL") or os.environ.get("EDITOR")
    if editor:
        return editor

    fallback = shutil.which(_FALLBACK_EDITOR)
    if fallback:
        return fallback

    raise DependencyError(
        "No editor found. Set $VISUAL or $EDITOR, or install vi."
    )


def edit_message(message: str) -> str:
    """Edit *message* in an external editor and return the edited text.

    The editor is resolved with :func:`resolve_editor`. The proposed message is
    written to a secure temporary file and nothing else (no staged diff, no
    repository metadata). The editor is invoked without a shell. The temporary
    file is cleaned up in a ``finally`` block where practical.

    Raises:
        DependencyError: if no editor is found or the editor exits non-zero
            without being cancelled.
        CancelError: if the user cancels with Ctrl+C during editing or the
            editor is killed by a signal.
        EmptyCommitMessageError: not raised here; callers must validate the
            returned text.
    """
    editor = resolve_editor()

    fd, path = tempfile.mkstemp(prefix="toolsmith-commit-message-", suffix=".txt")
    try:
        os.close(fd)
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(message)

        try:
            result = subprocess.run(
                [editor, path],
                check=False,
                capture_output=True,
                text=True,
            )
        except KeyboardInterrupt as exc:
            raise CancelError("Editor cancelled; no commit created.") from exc

        if result.returncode != 0:
            if result.returncode < 0:
                raise CancelError(
                    f"Editor cancelled by signal {-result.returncode}; no commit created."
                )
            stderr = result.stderr.strip() if result.stderr else ""
            detail = f": {stderr}" if stderr else ""
            raise DependencyError(
                f"Editor exited with status {result.returncode}{detail}. No commit created."
            )

        with open(path, "r", encoding="utf-8") as handle:
            return handle.read()
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
