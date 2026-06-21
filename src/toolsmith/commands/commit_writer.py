"""Commit Writer command orchestration."""

from __future__ import annotations

import argparse

from toolsmith import config
from toolsmith.git import diff as git_diff
from toolsmith.git import repository as git_repository


def run(args: argparse.Namespace) -> int:
    """Run the Commit Writer command up to the Phase 3 contract boundary.

    Phase 3 resolves the git repository root, validates that staged changes
    exist, and prepares a bounded staged diff. LLM/provider construction and
    commit/push creation remain deferred to later phases.
    """
    overrides: dict[str, object] = {}
    if args.model is not None:
        overrides["model"] = args.model
    overrides["no_push"] = args.no_push

    cfg = config.build_config(cli_overrides=overrides)

    if args.dry_run:
        print("Dry run: no commit or push will be created.")
        return 0

    # Phase 3: read-only git services. Any failure here propagates to the CLI
    # boundary before any LLM/provider is constructed.
    repo_root = git_repository.find_repository_root()
    git_diff.prepare_staged_diff(repo_root, cfg.max_diff_chars)

    # Phase 4+ will call the local LLM, present the accept/edit/reject flow,
    # and optionally create a commit/push.
    return 0
