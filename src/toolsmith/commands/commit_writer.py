"""Commit Writer command orchestration."""

from __future__ import annotations

import argparse

from toolsmith import config


def run(args: argparse.Namespace) -> int:
    """Run the Commit Writer command up to the Phase 2 contract boundary.

    Phase 2 validates and merges configuration but does not read git state,
    construct an LLM provider, or create a commit/push.
    """
    overrides: dict[str, object] = {}
    if args.model is not None:
        overrides["model"] = args.model
    overrides["no_push"] = args.no_push

    cfg = config.build_config(cli_overrides=overrides)

    if args.dry_run:
        print("Dry run: no commit or push will be created.")
        return 0

    # Phase 3+ will use cfg to read staged changes, call the local LLM, and
    # present the accept/edit/reject flow. No side effects beyond configuration
    # validation happen in Phase 2.
    return 0
