"""Commit Writer command orchestration."""

from __future__ import annotations

import argparse

from toolsmith import config, llm
from toolsmith.git import diff as git_diff
from toolsmith.git import repository as git_repository


def run(args: argparse.Namespace) -> int:
    """Run the Commit Writer command up to the Phase 4 contract boundary.

    Phase 4 resolves configuration, validates the git repository and staged
    changes, and constructs the shared LLM client through the provider
    factory. The actual prompt construction, generation, and user review
    remain deferred to later phases.
    """
    overrides: dict[str, object] = {}
    if args.model is not None:
        overrides["model"] = args.model
    overrides["no_push"] = args.no_push

    cfg = config.build_config(cli_overrides=overrides)

    if args.dry_run:
        print("Dry run: no commit or push will be created.")
        return 0

    # Read-only git services. Any failure here propagates to the CLI
    # boundary before any LLM/provider is constructed.
    repo_root = git_repository.find_repository_root()
    git_diff.prepare_staged_diff(repo_root, cfg.max_diff_chars)

    # Phase 4: construct the local LLM client through the shared factory.
    # Commands depend only on the shared :class:`llm.LLMClient` contract;
    # provider-specific transport lives in :mod:`toolsmith.llm.ollama`.
    llm.create_client(cfg.provider)

    # Phase 5+ will build the prompt, generate a message, present the
    # accept/edit/reject flow, and optionally create a commit/push.
    return 0
