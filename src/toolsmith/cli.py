"""toolsmith CLI entry point."""

from __future__ import annotations

import argparse
import sys

from toolsmith import __version__
from toolsmith.commands import commit_writer
from toolsmith.errors import CancelError, ToolsmithError, render_message


_CW_DESCRIPTION = """
Commit Writer: generate a git commit message from currently staged changes using a local LLM.

Preconditions:
  * Run this command inside a git repository.
  * Stage changes manually with `git add` before invoking `toolsmith cw`.
  * toolsmith reads only the staged index; unstaged changes are ignored.

Options:
  --no-push   Skip the "push current branch?" prompt after a successful commit.
  --dry-run   Preview behavior without creating a commit, push, or LLM call.
  --model     Override the LLM model identifier for this run only.

Examples:
  toolsmith cw
  toolsmith cw --no-push
  toolsmith cw --dry-run
  toolsmith cw --model llama3.1:latest

Safety:
  * No commit or push is created without your explicit approval.
  * No changes are staged or unstaged automatically.
  * All LLM processing uses the configured local provider.
"""


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toolsmith",
        description=(
            "A lightweight, modular, local-first CLI productivity assistant.\n\n"
            "Use `toolsmith cw` to generate a commit message from staged changes."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    cw_parser = subparsers.add_parser(
        "cw",
        help="Commit Writer: generate a commit message from staged changes.",
        description=_CW_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    cw_parser.add_argument(
        "--no-push",
        action="store_true",
        help="Do not prompt to push after a successful commit.",
    )
    cw_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would happen without creating a commit or push.",
    )
    cw_parser.add_argument(
        "--model",
        metavar="MODEL",
        help="Override the configured LLM model identifier for this run only.",
    )
    cw_parser.set_defaults(func=commit_writer.run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    try:
        return args.func(args)
    except KeyboardInterrupt:
        print("\nCancelled.", file=sys.stderr)
        return CancelError.exit_code
    except ToolsmithError as exc:
        print(f"Error: {render_message(exc)}", file=sys.stderr)
        return exc.exit_code


if __name__ == "__main__":
    sys.exit(main())
