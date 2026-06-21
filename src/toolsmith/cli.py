"""toolsmith CLI entry point."""

from __future__ import annotations

import argparse
import sys

from toolsmith import __version__
from toolsmith.commands import commit_writer


def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="toolsmith",
        description="A lightweight, local-first CLI productivity assistant.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    cw_parser = subparsers.add_parser(
        "cw",
        help="Commit Writer: generate a commit message from staged changes (placeholder).",
        description="Commit Writer: generate a commit message from staged changes (placeholder).",
    )
    cw_parser.set_defaults(func=commit_writer.run)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)

    if args.command is None:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
