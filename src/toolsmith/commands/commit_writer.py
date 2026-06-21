"""Commit Writer command orchestration."""

from __future__ import annotations

import argparse
import sys

from toolsmith import config, llm
from toolsmith.errors import GitError, PushError
from toolsmith.git import commit as git_commit
from toolsmith.git import diff as git_diff
from toolsmith.git import repository as git_repository
from toolsmith.prompts import commit_writer as commit_prompts
from toolsmith.ui import editor
from toolsmith.ui import prompts as ui_prompts


def _generate_message(
    cfg: config.Config,
    prepared: git_diff.PreparedDiff,
    client: llm.LLMClient,
) -> commit_prompts.CommitMessage:
    """Generate, clean, and validate a commit message from staged changes."""
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
    return validated


def _display_message(message: commit_prompts.CommitMessage) -> None:
    """Print the proposed message and any non-blocking warnings."""
    # Reassemble the conventional subject/body form for display.
    text = message.subject
    if message.body:
        text += "\n\n" + message.body
    print(text)


def run(
    args: argparse.Namespace,
    *,
    commit_service: git_commit.CommitService | None = None,
    push_service: git_commit.PushService | None = None,
) -> int:
    """Run the Commit Writer command through the accept/edit/reject boundary.

    The command resolves configuration, validates the git repository and
    staged changes, builds a deterministic prompt, calls the configured local
    LLM, cleans and validates the generated message, displays it, and asks
    the user to accept, edit, or reject. After explicit acceptance it creates
    a real git commit using ``git commit -F <message-file>``, preserving
    normal hooks and signing. When configuration allows, it then prompts
    whether to run an ordinary ``git push``; only an explicit yes attempts the
    push. A push failure is reported separately and does not roll back the
    successful commit.

    Dry-run mode performs generation and display but exits before approval,
    commit, or push. Real commit and push mutation use the default
    :class:`GitCommitService` and :class:`GitPushService` unless other
    services are injected (primarily for tests).
    """
    overrides: dict[str, object] = {}
    if args.model is not None:
        overrides["model"] = args.model
    overrides["no_push"] = args.no_push

    cfg = config.build_config(cli_overrides=overrides)

    # Read-only git services. Any failure here propagates to the CLI
    # boundary before any LLM/provider is constructed.
    repo_root = git_repository.find_repository_root()
    prepared = git_diff.prepare_staged_diff(repo_root, cfg.max_diff_chars)

    # Phase 4: construct the local LLM client through the shared factory.
    client = llm.create_client(cfg.provider)

    validated = _generate_message(cfg, prepared, client)

    for warning in validated.warnings:
        print(warning, file=sys.stderr)

    _display_message(validated)

    if args.dry_run:
        print("Dry run: no commit or push will be created.")
        return 0

    # Phase 6: interactive accept/edit/reject loop.
    message_text = validated.subject
    if validated.body:
        message_text += "\n\n" + validated.body

    while True:
        choice = ui_prompts.prompt_accept_edit_reject(message_text)
        if choice == "edit":
            edited = editor.edit_message(message_text)
            cleaned = commit_prompts.clean_commit_message(edited)
            revalidated = commit_prompts.validate_commit_message(cleaned)
            message_text = revalidated.subject
            if revalidated.body:
                message_text += "\n\n" + revalidated.body
            for warning in revalidated.warnings:
                print(warning, file=sys.stderr)
            continue

        # choice == "accept"
        break

    # Phase 7: create the real commit, or use an injected service for tests.
    service = commit_service or git_commit.GitCommitService()
    commit_result = service.create_commit(
        repository_root=repo_root,
        message=message_text,
    )

    if not commit_result.success:
        raise GitError(commit_result.message or "Commit failed.")

    print(commit_result.message or "Commit created.")

    if cfg.prompt_push:
        push_svc = push_service or git_commit.GitPushService()
        if ui_prompts.prompt_push():
            push_result = push_svc.push(repository_root=repo_root)
            if not push_result.success:
                raise PushError(
                    f"Commit was created, but push failed: {push_result.message}"
                )
            print(push_result.message or "Push completed.")

    return 0
