# toolsmith Agent Guidance

**Status:** Phase 6 interactive review, editor flow, and dry-run behavior
**Maintainer:** Repository maintainer (single owner until team growth is documented)
**Requirement sources:** `planning/req_spec.md`, `planning/scope.md`, `planning/project_implementation_plan.md`

This file is a living architecture and ownership record. Any change to command structure, safety behavior, provider policy, test commands, configuration, or release procedure must update this file and `GUARDRAILS.md` in the same change, then receive maintainer review before merging.

---

## Phase 1–5 objective

Establish the repository contract and the smallest installable Python `toolsmith` package skeleton, add the read-only git boundary and the local-only LLM boundary, then implement the Commit Writer prompt builder and generated-message cleanup/validation used by `toolsmith cw`.

Phase 1 delivered:

- Repository governance (`agents/AGENTS.md`, `agents/GUARDRAILS.md`).
- A `src/` layout Python package with importable subpackages.
- A minimal `toolsmith` console entry point that starts cleanly and returns placeholder help.
- pytest configuration and a smoke-test suite proving imports and help work.
- Documented stack choices (Python versions, build backend, CLI approach, dependencies).

Phase 2 delivered:

- Stable `toolsmith --help` and `toolsmith cw --help`.
- `--no-push`, `--dry-run`, and optional `--model` CLI options.
- Built-in defaults, optional user TOML loading from `~/.config/toolsmith/config.toml`, and validated precedence (CLI > user config > defaults).
- A centralized error taxonomy and exit-code mapping used by the CLI boundary.

Phase 3 delivered:

- Git availability detection and repository root resolution from any subdirectory.
- Staged-change detection using only `git diff --cached` data.
- Staged file summary with status parsing for additions, modifications, deletions, renames, and copies.
- Binary-file identification from git `--numstat` metadata; working-tree binary contents are never opened.
- Deterministic staged-diff truncation at `max_diff_chars` with an explicit marker.
- Mapped actionable errors for missing git, outside-repo, no staged changes, and git command failure.

Phase 4 delivered:

- Shared `LLMRequest`, `LLMResponse`, and `LLMClient` contract in `llm/base.py`.
- A single local Ollama-compatible adapter in `llm/ollama.py` using only standard-library HTTP.
- Provider factory in `llm/__init__.py` limited to the supported local Phase 1 provider (`ollama`).
- Actionable error mapping for connection failure, unavailable runtime/model, timeout, malformed payload, and empty output.
- A fake LLM client utility for command tests, and default pytest tests that pass without Ollama, network access, or a downloaded model.

Phase 5 delivered:

- Deterministic Commit Writer prompt builder in `prompts/commit_writer.py`.
- Anti-hallucination constraints and required output shape in the prompt.
- Conservative commit-message cleanup for common model wrappers.
- Validation that rejects empty output and emits a non-blocking warning for subjects over 72 characters.
- Focused unit tests for prompt content, cleanup/validation, and mocked-LLM orchestration.

Phase 5 does **not** implement interactive review, editor invocation, commit/push creation, or staging behavior.

Phase 6 delivered:

- Interactive accept/edit/reject prompts in `ui/prompts.py`. The proposed message is always displayed first; blank or invalid input reprompts; reject and EOF return `CancelError` with a clear no-commit message; Ctrl+C propagates to the CLI boundary.
- External editor resolution in `ui/editor.py`: `$VISUAL`, then `$EDITOR`, then the documented executable fallback `vi`. The editor is invoked without a shell and receives a temporary file containing **only** the proposed commit message. The temporary file is removed in a `finally`-style path. Non-zero editor exits become `DependencyError`; signal termination and Ctrl+C become `CancelError`.
- The Commit Writer orchestration in `commands/commit_writer.py` now displays the generated message, enters an accept/edit/reject loop, re-cleans and re-validates edited messages, and calls fake commit/push services so the full interactive flow is testable without mutating any repository.
- `--dry-run` now performs generation, cleanup, warning, and display, then prints a dry-run notice and exits successfully before any approval, commit, or push prompt.
- Unit tests for prompts, editor, orchestration, and CLI dry-run/reject/cancellation paths.

Phase 6 does **not** create real git commits or pushes. Real mutation belongs to Phase 7.

---

## Architecture map

```text
agents/
  AGENTS.md
  GUARDRAILS.md
pyproject.toml
README.md
src/
  toolsmith/
    __init__.py          # package version
    cli.py               # argparse root command and subcommand registration
    config.py            # defaults, user TOML loading, validation, precedence
    errors.py            # error taxonomy and exit-code mapping
    commands/
      __init__.py
      commit_writer.py   # cw command orchestration (Phases 5-6: config + read-only git + shared LLM factory + interactive review + fake commit/push services)
    git/
      __init__.py
      repository.py      # repository detection, root resolution, git subprocess runner (Phase 3)
      diff.py            # staged summary/diff collection and truncation (Phase 3)
      commit.py          # commit/push service interface + Phase 6 fake implementations (Phase 7: real services)
    llm/
      __init__.py        # provider factory and public exports
      base.py            # shared LLM request/response/client contract (Phase 4)
      ollama.py          # local Ollama-compatible adapter (Phase 4)
    prompts/
      __init__.py
      commit_writer.py   # prompt construction and message cleanup (Phase 5)
    ui/
      __init__.py
      prompts.py         # terminal accept/edit/reject prompts (Phase 6, implemented)
      editor.py          # $VISUAL/$EDITOR resolution and invocation (Phase 6, implemented)
tests/
  unit/                  # unit, CLI, and mocked-LLM tests
  integration/           # temporary-git repository tests
```

Boundary rules:

- `cli.py` – owns argument parsing, subcommand routing, and top-level help. Heavy imports and service construction are deferred to subcommands so `--help` starts quickly. The CLI boundary catches `ToolsmithError`, maps it to the documented exit code, and prints a concise message.
- `commands/commit_writer.py` – orchestrates the Commit Writer workflow. It validates configuration, resolves the git repository root, prepares a bounded staged diff, builds a deterministic prompt, sends the request through the shared LLM client, and cleans, validates, and displays the generated message. It does not contain subprocess details, provider transport, config parsing, prompt text, or editor/interactive logic.
- `git/` – owns all git subprocess calls. Uses argument arrays, never shell interpolation. Returns typed/domain results or raises mapped `toolsmith` errors.
- `llm/base.py` – defines the shared `LLMClient` contract and request/response types. Commands depend only on this protocol.
- `llm/ollama.py` – is the sole Phase 1 provider adapter. It maps transport and payload failures to actionable responses without leaking Ollama-specific exceptions.
- `llm/__init__.py` – exposes the shared contract and a provider factory that accepts only the supported local provider.
- `prompts/commit_writer.py` – owns compact prompt construction and message cleanup/validation helpers.
- `ui/` – owns terminal prompts and editor invocation. It performs no git or LLM work.
- `config.py` – merges built-in defaults, user TOML at `~/.config/toolsmith/config.toml`, and supported per-command overrides, with explicit validation.
- `errors.py` – defines the error taxonomy and stable exit-code mapping used at the CLI boundary.

---

## Stack decisions

- **Language:** Python 3.10 or newer.
- **Build backend:** `setuptools` (widely available, minimal, supports `src/` layout).
- **CLI approach:** Python standard-library `argparse`. No external CLI framework is required for Phase 1; this keeps dependencies minimal and startup fast.
- **Test runner:** `pytest` (canonical for Phase 1 automated tests).
- **Runtime dependencies:** none in Phase 1. Phase 2 adds `tomli` as a conditional runtime dependency for Python 3.10 TOML parsing fallback; Python 3.11+ uses the standard-library `tomllib`.
- **Development dependencies:** `pytest` for automated testing.
- **Configuration format:** TOML at `~/.config/toolsmith/config.toml`.
- **Local provider:** Ollama-compatible adapter in Phase 4 using only standard-library `urllib`. No cloud provider, fallback, or plugin system is introduced in Phase 1–4.
- **Editor resolution:** resolves `$VISUAL`, then `$EDITOR`, then the documented executable fallback `vi`. If no editor is found, the command fails with a `DependencyError` and no commit is attempted.

---

## Canonical test commands

These are the canonical automated test commands for every Phase 1 validation and release gate:

```bash
pytest
pytest tests/unit
pytest tests/integration
```

Manual tests and optional local-provider smoke tests are documented in `planning/project_implementation_plan.md` and must be run in disposable repositories.

---

## Commands

### Current

- `toolsmith --help` – root help.
- `toolsmith cw --help` – Commit Writer help, including staged-change preconditions, options, examples, and safety notes.
- `toolsmith cw` – parses configuration and options; resolves the git repository root; detects and prepares staged changes using only `git diff --cached` data; builds a deterministic prompt from the staged summary and bounded diff; sends it to the configured local LLM; cleans and validates the response; prints any non-blocking warning; and displays the proposed commit message. Does not implement interactive accept/edit/reject, commit, push, stage, or unstage.

### Phase 2 options

- `--no-push` – skip the post-commit push prompt.
- `--dry-run` – preview behavior without creating a commit, push, LLM call, or reading git state.
- `--model MODEL` – override the configured model identifier for this run only. This changes only the model string sent to the configured local provider; it never changes the provider class, endpoint policy, or local-only policy.

### Future commands (not implemented in Phase 1–4)

The following are explicitly reserved for future planning. They must not be implemented, partially wired, or given speculative dependencies during Phase 1–4:

- `toolsmith mail` – Email Improver
- `toolsmith req` – Requirements Reviewer
- `toolsmith err` – Error Explainer

Implementation of any future command requires a revised scope/requirements document and a separate implementation plan.

### Phase 6 non-goals (real mutation remains Phase 7)

- Real `git commit` or `git push` creation (Phase 7).
- Hook bypass, signing management, or automatic staging/unstaging.
- Regeneration, non-interactive mode, additional providers, or future commands.


---

## Exit-code mapping

The CLI boundary uses these stable exit codes from `toolsmith.errors`:

| Code | Meaning | Exception type |
|------|---------|----------------|
| `0`  | Success | – |
| `1`  | General failure | `ToolsmithError` |
| `2`  | User rejected/cancelled | `CancelError` |
| `3`  | Invalid usage/environment/config | `UsageError` |
| `4`  | External dependency failure | `DependencyError` |

Phase 3 maps the following git errors under `UsageError`/`DependencyError`:

- `NoRepositoryError(UsageError)` – current directory is not inside a git repository.
- `NoStagedChangesError(UsageError)` – no staged changes in the index.
- `GitError(DependencyError)` – git subprocess failure or unexpected output.

Phase 4 maps LLM adapter failures under `DependencyError` (via `require_success()`). Provider transport failures are converted to actionable responses by the Ollama adapter before reaching command orchestration.

---

## Maintainer ownership and update triggers

- **Owner:** The repository maintainer owns this file and `GUARDRAILS.md`.
- **Review gate:** Any PR that changes command structure, safety behavior, provider policy, test commands, configuration handling, or release procedure must also update this file and `GUARDRAILS.md`, and must receive maintainer review before merge.
- **Release checklist:** Before every release, confirm that:
  1. This file and `GUARDRAILS.md` still match the implementation.
  2. The architecture map matches the file tree.
  3. The canonical pytest commands still pass.
  4. No Phase 5 non-goal has entered dependencies or code.

---

## Deferred decisions

The following decisions are intentionally deferred to later phases and must not be anticipated in Phase 4 code or dependencies:

- Direct `cw` executable alias.
- Conventional Commits mode.
- Regenerate action.
- Non-interactive operation.
- Additional local providers or provider plugin discovery.
- Cloud inference or cloud fallback.
- Commit-history or repository-wide semantic analysis.
- Automatic stage/unstage, branch creation, code changes, PR creation, issue integration, or git configuration/signing management.
- Agent frameworks, autonomous execution, background services, RAG, embeddings, vector stores, telemetry, web UI, chat UI, voice UI, and multi-user features.
