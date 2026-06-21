# toolsmith Phase 2 Guardrails

**Status:** Phase 2 invariants
**Maintainer:** Repository maintainer
**Requirement sources:** `planning/project_implementation_plan.md` Section 3, `planning/req_spec.md`, `planning/scope.md`

This file records the safety and scope invariants that every implementation phase must preserve. Any change that weakens, removes, or bypasses a guardrail requires a formal requirements update and maintainer review before merge.

---

## LLM and data-locality guardrails

- **Local-only LLM processing.** All LLM processing must be local in Phase 1/2. toolsmith must not send diffs, filenames, repository metadata, or commit messages to a cloud service and must not silently fall back to one.
- **No cloud default.** The default provider configuration must assume local model execution. No cloud provider may be configured or implied by defaults.
- **Staged-diff-only input.** Only the staged git index is input to prompt preparation. Never add unstaged changes, repository history, repository-wide analysis, or unrelated files to the prompt.
- **No diff persistence.** Do not persist staged diffs in logs, telemetry, caches, or durable temporary files.
- **No telemetry.** Phase 1/2 must not include telemetry, usage analytics, or network calls unrelated to the configured local provider.
- **Model override is local-only.** The `--model` option changes only the model identifier passed to the configured local provider. It must never change the provider class, endpoint policy, or local-only policy.

---

## Git mutation and user-control guardrails

- **No automatic staging/unstaging.** toolsmith must not stage, unstage, modify, or generate application code on the user's behalf as part of `toolsmith cw`.
- **No commit before explicit approval.** Never create a commit before the generated or edited message has been displayed and the user has explicitly accepted it.
- **Reject/cancel/error leaves the repository unchanged.** Reject, cancellation, editor failure, LLM failure, and any pre-approval error must leave the repository uncommitted and must not mutate the index, working tree, branch, remotes, or git configuration.
- **No automatic push.** Never push without explicit confirmation in the current invocation. Empty input at the push prompt means no. Never force push.
- **Preserve git hooks and signing.** Preserve normal git hooks and the user's existing signing configuration; do not bypass or manage either.
- **Commit exactly the staged state.** Commit exactly the index state git sees when the commit command runs. Never stage/unstage or implement partial-commit logic.

---

## Scope and dependency guardrails

- **No cloud SDKs or agent frameworks.** Dependencies must not include cloud SDKs, agent frameworks, background-service frameworks, telemetry libraries, RAG/embedding/vector-store libraries, web/chat/voice UI frameworks, workflow orchestrators, or public API clients.
- **No future-command implementation.** Do not implement Email Improver, Error Explainer, Requirements Reviewer, or any command other than Commit Writer in Phase 1/2. Keep future extensibility to clear command and shared-service boundaries; do not build speculative abstractions for commands that do not yet exist.
- **No background services or daemons.** Phase 1/2 must not include long-running background services, daemons, or servers.
- **Minimal dependencies.** Prefer the standard library. Each non-development dependency added in a later phase must have an explicit Phase 1+ justification recorded in `AGENTS.md`. Phase 2 adds `tomli` only as a Python 3.10 fallback for the required TOML config format.

---

## Review and release triggers

Review this file:

- Whenever command structure, safety behavior, provider policy, configuration, or release procedure changes.
- Before every release, as part of the release checklist.
- Whenever a new dependency is proposed, to confirm no cloud SDK, telemetry, agent framework, background service, or future-command dependency is introduced.

---

## Phase 1/2 non-goals

The following stay outside Phase 1/2 unless the requirements documents are formally revised:

- Direct `cw` executable alias.
- Conventional Commits mode.
- Regenerate action.
- Non-interactive operation.
- Additional local providers or provider plugin discovery.
- Cloud inference or cloud fallback of any kind.
- Commit-history or repository-wide semantic analysis.
- Automatic stage/unstage, branch creation, code changes, PR creation, issue integration, or git configuration/signing management.
- Agent frameworks, autonomous execution, background services, RAG, embeddings, vector stores, telemetry, web UI, chat UI, voice UI, and multi-user features.
- Full secret scanning or generated-file classification.
- Email Improver, Error Explainer, Requirements Reviewer, or any other command.
