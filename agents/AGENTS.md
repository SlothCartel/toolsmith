# toolsmith Agent Guidance

**Status:** Phase 1 scaffold  
**Maintainer:** Repository maintainer (single owner until team growth is documented)  
**Requirement sources:** `planning/req_spec.md`, `planning/scope.md`, `planning/project_implementation_plan.md`  

This file is a living architecture and ownership record. Any change to command structure, safety behavior, provider policy, test commands, configuration, or release procedure must update this file and `GUARDRAILS.md` in the same change, then receive maintainer review before merging.

---

## Phase 1 objective

Establish the repository contract and the smallest installable Python `toolsmith` package skeleton before Commit Writer feature implementation begins.

Phase 1 delivers:

- Repository governance (`agents/AGENTS.md`, `agents/GUARDRAILS.md`).
- A `src/` layout Python package with importable subpackages.
- A minimal `toolsmith` console entry point that starts cleanly and returns placeholder help.
- pytest configuration and a smoke-test suite proving imports and help work.
- Documented stack choices (Python versions, build backend, CLI approach, dependencies).

Phase 1 does **not** implement `toolsmith cw` behavior, LLM provider behavior, git diff/commit/push behavior, or any future command.

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
    config.py            # defaults, user TOML loading, validation (Phase 2+)
    errors.py            # error taxonomy and exit-code mapping (Phase 2+)
    commands/
      __init__.py
      commit_writer.py   # cw command orchestration (placeholder)
    git/
      __init__.py
      repository.py      # repository detection and root resolution (Phase 3)
      diff.py            # staged summary/diff collection (Phase 3)
      commit.py          # commit and push creation (Phase 7)
    llm/
      __init__.py
      base.py            # shared LLM request/response/client contract (Phase 4)
      ollama.py          # local Ollama-compatible adapter (Phase 4)
    prompts/
      __init__.py
      commit_writer.py   # prompt construction and message cleanup (Phase 5)
    ui/
      __init__.py
      prompts.py         # terminal accept/edit/reject prompts (Phase 6)
      editor.py          # $VISUAL/$EDITOR invocation (Phase 6)
tests/
  unit/                  # unit, CLI, and mocked-LLM tests
  integration/           # temporary-git repository tests
```

---

## Module responsibilities

- `cli.py` – owns argument parsing, subcommand routing, and top-level help. Heavy imports and service construction are deferred to subcommands so `--help` starts quickly.
- `commands/commit_writer.py` – orchestrates the Commit Writer workflow. It does not contain subprocess details, provider transport, config parsing, prompt text, or editor process logic.
- `git/` – owns all git subprocess calls. Uses argument arrays, never shell interpolation. Returns typed/domain results or raises mapped `toolsmith` errors.
- `llm/base.py` – defines the shared `LLMClient` contract and request/response types. `llm/ollama.py` is the sole Phase 1 provider adapter.
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
- **Runtime dependencies:** none. All Phase 1 scaffold code uses the Python standard library.
- **Development dependencies:** `pytest` for automated testing.
- **Configuration format:** TOML at `~/.config/toolsmith/config.toml` (planned for Phase 2). Standard-library TOML support is available via `tomllib` on Python 3.11+; a minimal fallback strategy will be chosen in Phase 2 if Python 3.10 compatibility is retained.
- **Local provider:** Ollama-compatible adapter planned for Phase 4. No cloud provider, fallback, or plugin system is introduced in Phase 1.
- **Editor resolution:** planned to resolve `$VISUAL`, then `$EDITOR`, then a documented executable fallback in Phase 6. If no editor is found, fail without committing.

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

### Phase 1 only

- `toolsmith cw` – registered as a placeholder; does not perform git, LLM, commit, push, staging, or mutation behavior in Phase 1.

### Future commands (not implemented in Phase 1)

The following are explicitly reserved for future planning. They must not be implemented, partially wired, or given speculative dependencies during Phase 1:

- `toolsmith mail` – Email Improver
- `toolsmith req` – Requirements Reviewer
- `toolsmith err` – Error Explainer

Implementation of any future command requires a revised scope/requirements document and a separate implementation plan.

---

## Maintainer ownership and update triggers

- **Owner:** The repository maintainer owns this file and `GUARDRAILS.md`.
- **Review gate:** Any PR that changes command structure, safety behavior, provider policy, test commands, configuration handling, or release procedure must also update this file and `GUARDRAILS.md`, and must receive maintainer review before merge.
- **Release checklist:** Before every release, confirm that:
  1. This file and `GUARDRAILS.md` still match the implementation.
  2. The architecture map matches the file tree.
  3. The canonical pytest commands still pass.
  4. No Phase 1 non-goal has entered dependencies or code.

---

## Deferred decisions

The following decisions are intentionally deferred to later phases and must not be anticipated in Phase 1 code or dependencies:

- Direct `cw` executable alias.
- Conventional Commits mode.
- Regenerate action.
- Non-interactive operation.
- Additional local providers or provider plugin discovery.
- Cloud inference or cloud fallback.
- Commit-history or repository-wide semantic analysis.
- Automatic stage/unstage, branch creation, code changes, PR creation, issue integration, or git configuration/signing management.
- Agent frameworks, autonomous execution, background services, RAG, embeddings, vector stores, telemetry, web UI, chat UI, voice UI, and multi-user features.
