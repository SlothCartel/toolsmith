# toolsmith Phase 1 Guardrails

**Status:** Phase 9 release readiness
**Phase 9 review:** all guardrails were confirmed against the final implementation and release checklist.
**Maintainer:** Repository maintainer
**Requirement sources:** `planning/project_implementation_plan.md` Section 3, `planning/req_spec.md`, `planning/scope.md`

This file records the safety and scope invariants that every implementation phase must preserve. Any change that weakens, removes, or bypasses a guardrail requires a formal requirements update and maintainer review before merge.

---

## LLM and data-locality guardrails

- **Local-only LLM processing.** All LLM processing must be local in Phase 1. toolsmith must not send diffs, filenames, repository metadata, or commit messages to a cloud service and must not silently fall back to one.
- **No cloud default.** The default provider configuration must assume local model execution. No cloud provider may be configured or implied by defaults.
- **Staged-diff-only input.** Only the staged git index is input to prompt preparation. Never add unstaged changes, repository history, repository-wide analysis, or unrelated files to the prompt.
- **No diff persistence.** Do not persist staged diffs in logs, telemetry, caches, or durable temporary files.
- **No telemetry.** Phase 1 must not include telemetry, usage analytics, or network calls unrelated to the configured local provider.
- **Model override is local-only.** The `--model` option changes only the model identifier passed to the configured local provider. It must never change the provider class, endpoint policy, or local-only policy.
- **Supported provider is explicit and local.** The only Phase 1 provider is the local Ollama-compatible adapter. Provider selection must reject unsupported providers before any generation attempt. No cloud, remote, or network fallback may be attempted.

---

## Git mutation and user-control guardrails

- **Read-only git services in Phase 3–5.** All git subprocess calls in Phase 3–5 use only `git diff --cached` and `git rev-parse --show-toplevel`. No Phase 3–5 code stages, unstages, modifies, commits, pushes, branches, reads working-tree file contents directly, or changes git configuration.
- **No automatic staging/unstaging.** toolsmith must not stage, unstage, modify, or generate application code on the user's behalf as part of `toolsmith cw`.
- **No commit before explicit approval.** Never create a commit before the generated or edited message has been displayed and the user has explicitly accepted it.
- **Reject/cancel/error leaves the repository unchanged before approval.** Reject, cancellation, editor failure, LLM failure, and any pre-approval error must leave the repository uncommitted and must not mutate the index, working tree, branch, remotes, or git configuration.
- **Commit exactly the staged state.** Commit exactly the index state git sees when the commit command runs. Never stage/unstage or implement partial-commit logic.
- **Preserve git hooks and signing.** Preserve normal git hooks and the user's existing signing configuration; do not bypass or manage either.
- **No hook-bypass or signing-management flags.** The commit service must not pass `--no-verify`, `--no-gpg-sign`, `-S`, `-s`, or any equivalent flag.
- **No automatic push.** Never push without explicit confirmation in the current invocation. Empty input at the push prompt means no. Never force push.
- **Ordinary push only.** The push service must run only ordinary `git push`. `--force`, `--force-with-lease`, and `-f` are forbidden.
- **Push failure does not roll back the commit.** A successful commit is intentionally preserved when the subsequent push fails. The failure is reported separately and the exit code is non-zero.
- **Dry-run does not approve, commit, or push.** `--dry-run` may generate and display the proposed message, but it must exit before any approval prompt, commit service call, or push prompt.
- **Edited messages must be re-displayed and re-validated before commit.** An edited message is cleaned and validated again; an empty or invalid edited message cannot proceed to commit or push.
- **Ctrl+C at the push prompt leaves the commit intact.** A keyboard interrupt at the push prompt cancels the push but does not undo the just-created commit.

---

## Phase 7 commit/push implementation notes

Phase 7 turns the previously fake commit/push services into real ones while preserving every guardrail above:

- `GitCommitService` writes the accepted message to a secure temporary file and runs `git commit -F <message-file>` as a subprocess argument array. The temporary file is cleaned up on success and failure.
- `GitPushService` runs `git push` as a subprocess argument array with no force-related flags.
- The command orchestration only reaches the commit service after the accept/edit/reject loop returns `accept`, and only reaches the push service after a successful commit and an explicit yes at the prompt (unless `--no-push` or `--dry-run` applies).
- Commit failure raises `GitError`; push failure raises `PushError`, which reports both the failed push and the fact that the commit was created and not rolled back.

---

## Scope and dependency guardrails

- **No cloud SDKs or agent frameworks.** Dependencies must not include cloud SDKs, agent frameworks, background-service frameworks, telemetry libraries, RAG/embedding/vector-store libraries, web/chat/voice UI frameworks, workflow orchestrators, or public API clients.
- **No future-command implementation.** Do not implement Email Improver, Error Explainer, Requirements Reviewer, or any command other than Commit Writer in Phase 1. Keep future extensibility to clear command and shared-service boundaries; do not build speculative abstractions for commands that do not yet exist.
- **No background services or daemons.** Phase 1 must not include long-running background services, daemons, or servers.
- **No provider plugin system.** Phase 1 supports exactly one local provider. Do not add plugin discovery, dynamic provider loading, or a generic provider registry.
- **No model download or runtime management.** Phase 1 does not download, install, start, or manage the local LLM runtime or model files. The user is responsible for having Ollama and the configured model available.
- **No retry chain across providers.** Phase 1 does not retry failed LLM calls or fall back to alternative providers.
- **Minimal dependencies.** Prefer the standard library. Each non-development dependency added in a later phase must have an explicit Phase 1+ justification recorded in `AGENTS.md`. Phase 2 adds `tomli` only as a Python 3.10 fallback for the required TOML config format.

---

## Review and release triggers

Review this file:

- Whenever command structure, safety behavior, provider policy, configuration, or release procedure changes.
- Before every release, as part of the release checklist.
- Whenever a new dependency is proposed, to confirm no cloud SDK, telemetry, agent framework, background service, or future-command dependency is introduced.
- Whenever the LLM contract, provider factory, or adapter behavior changes.
- Whenever the commit or push service implementation changes.

---

## Phase 1 non-goals

The following stay outside Phase 1 unless the requirements documents are formally revised:

- Direct `cw` executable alias.
- Conventional Commits mode.
- Regenerate action.
- Non-interactive operation.
- Additional local providers or provider plugin discovery.
- Cloud inference or cloud fallback of any kind.
- Model download, installation, or runtime management.
- Retrying across providers.
- Commit-history or repository-wide semantic analysis.
- Automatic stage/unstage, branch creation, code changes, PR creation, issue integration, or git configuration/signing management.
- Agent frameworks, autonomous execution, background services, RAG, embeddings, vector stores, telemetry, web UI, chat UI, voice UI, and multi-user features.
- Full secret scanning or generated-file classification.
- Email Improver, Error Explainer, Requirements Reviewer, or any other command.
- Force push or force-with-lease.
