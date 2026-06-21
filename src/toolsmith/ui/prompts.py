"""Terminal accept/edit/reject prompts (Phase 6)."""

from __future__ import annotations

from toolsmith.errors import CancelError


def _normalize_input(text: str) -> str:
    """Return lowercased, whitespace-stripped user input."""
    return text.strip().lower()


def prompt_accept_edit_reject(message: str) -> str:
    """Prompt the user to accept, edit, or reject the proposed message.

    The message is always displayed before acceptance can be recorded.

    Accept responses:
      * a / accept
      * e / edit
      * r / reject

    Blank or invalid input reprompts and never accepts. Rejection or EOF
    raises :class:`CancelError` with a clear no-commit message. A keyboard
    interrupt propagates as :class:`KeyboardInterrupt` so the CLI boundary can
    return the documented cancellation exit code.
    """
    print("\nProposed commit message:")
    print("---")
    print(message)
    print("---")

    while True:
        try:
            choice = input("Accept (a), Edit (e), or Reject (r)? ")
        except EOFError:
            raise CancelError("Input closed; no commit created.")
        except KeyboardInterrupt:
            raise

        normalized = _normalize_input(choice)
        if normalized in {"a", "accept"}:
            return "accept"
        if normalized in {"e", "edit"}:
            return "edit"
        if normalized in {"r", "reject"}:
            raise CancelError("Commit rejected; no commit created.")

        print("Invalid choice. Please enter 'a' to accept, 'e' to edit, or 'r' to reject.")


def prompt_push() -> bool:
    """Ask whether to push the current branch.

    Only an explicit 'y' or 'yes' returns True. Blank input or any other
    response means no.
    """
    try:
        choice = input("Push current branch? [y/N] ")
    except (EOFError, KeyboardInterrupt):
        return False

    normalized = _normalize_input(choice)
    return normalized in {"y", "yes"}
