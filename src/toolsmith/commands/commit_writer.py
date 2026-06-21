"""Commit Writer command orchestration."""

from __future__ import annotations

import argparse
import sys

from toolsmith import config, llm
from toolsmith.git import diff as git_diff
from toolsmith.git import repository as git_repository
from toolsmith.prompts import commit_writer as commit_prompts


def run(args: argparse.Namespace) -> int:
    """Run the Commit Writer command up to the Phase 5 contract boundary.

    Phase 5 resolves configuration, validates the git repository and staged
    changes, builds a deterministic prompt, calls the configured local LLM,
    cleans and validates the generated message, prints any non-blocking
    warning, and displays the proposed message. The interactive
    accept/edit/reject flow, commit creation, and push behavior remain
    deferred to later phases.
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
    prepared = git_diff.prepare_staged_diff(repo_root, cfg.max_diff_chars)

    # Phase 4: construct the local LLM client through the shared factory.
    # Commands depend only on the shared :class:`llm.LLMClient` contract;
    # provider-specific transport lives in :mod:`toolsmith.llm.ollama`.
    client = llm.create_client(cfg.provider)

    # Phase 5: build the prompt, generate the message, and clean/validate it.
    request = llm.LLMRequest(
        prompt=commit_prompts.build_commit_prompt(prepared),
        model=cfg.model,
        temperature=cfg.temperature,
        max_tokens=cfg.max_tokens,
        timeout_seconds=cfg.timeout_seconds,
    )
    response = client.generate(request)
    raw_message = llm.require_success(response)

    cleaned_message = commit_prompts.clean_commit_message(raw_message)
    validated = commit_prompts.validate_commit_message(cleaned_message)

    for warning in validated.warnings:
        print(warning, file=sys.stderr)

    print(cleaned_message)

    # Phase 6+ will add the accept/edit/reject flow and commit/push creation.
    return 0
