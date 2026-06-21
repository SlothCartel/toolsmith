# toolsmith

A lightweight, modular, local-first command-line productivity assistant for developers.

**Phase 1** delivers the **Commit Writer** command:

```bash
toolsmith cw
```

It reads the currently staged git changes, asks a local LLM for a commit message,
displays the proposed message, and lets you **accept**, **edit**, or **reject** it.
Only after explicit approval does it create a commit. After a successful commit it
can optionally ask whether to push the current branch. Push defaults to **no**.

---

## Table of contents

1. [What it does](#what-it-does)
2. [Prerequisites](#prerequisites)
3. [Installation](#installation)
4. [Local provider setup](#local-provider-setup)
5. [Configuration](#configuration)
6. [Workflow](#workflow)
7. [Command options](#command-options)
8. [Exit codes](#exit-codes)
9. [Troubleshooting](#troubleshooting)
10. [Privacy and safety](#privacy-and-safety)
11. [Development and tests](#development-and-tests)
12. [Limitations and non-goals](#limitations-and-non-goals)

---

## What it does

`toolsmith cw` generates a plain git-style commit message from the changes you have
already staged with `git add`. It sends a compact prompt to a local LLM running on
your machine, shows you the result, and gives you control over whether to use it.

The command is intentionally simple and local-only. It does not stage files, modify
code, or push without your explicit confirmation.

---

## Prerequisites

- **Python** 3.10 or newer.
- **git** installed and on `PATH`.
- A local, Ollama-compatible LLM runtime running on `localhost:11434` (for real
  generation). The default automated test suite does not require a runtime.

---

## Installation

Install in editable mode with test dependencies:

```bash
git clone <repository-url> toolsmith
cd toolsmith
pip install -e ".[dev]"
```

After installation, the `toolsmith` console entry point is available:

```bash
toolsmith --help
toolsmith cw --help
```

If you are running from the repository without installing, use `PYTHONPATH=src`:

```bash
PYTHONPATH=src python -m toolsmith.cli --help
PYTHONPATH=src python -m toolsmith.cli cw --help
```

---

## Local provider setup

`toolsmith` targets a local Ollama-compatible runtime by default. Before running
`toolsmith cw` with a live provider:

1. Start Ollama (or an Ollama-compatible local server) on `localhost:11434`.
2. Pull a model you want to use, for example:

   ```bash
   ollama pull qwen2.5-coder:7b
   ```

3. Make sure the model name matches the value in `~/.config/toolsmith/config.toml`
   (see below).

If no local runtime is available, `toolsmith cw` exits with an actionable error and
does not attempt any cloud fallback.

---

## Configuration

User configuration is optional and lives at:

```text
~/.config/toolsmith/config.toml
```

If the file is missing, `toolsmith` uses the built-in defaults.

### Example config

```toml
[llm]
provider = "ollama"
model = "qwen2.5-coder:7b"
timeout_seconds = 20
temperature = 0.2
max_tokens = 512

[commit_writer]
max_diff_chars = 12000
prompt_push = true
```

### Built-in defaults

| Section | Field | Default |
|---------|-------|---------|
| `[llm]` | `provider` | `ollama` |
| `[llm]` | `model` | `qwen2.5-coder:7b` |
| `[llm]` | `timeout_seconds` | `20` |
| `[llm]` | `temperature` | `0.2` |
| `[llm]` | `max_tokens` | `512` |
| `[commit_writer]` | `max_diff_chars` | `12000` |
| `[commit_writer]` | `prompt_push` | `true` |

### Precedence

1. CLI options (`--model`, `--no-push`)
2. User config (`~/.config/toolsmith/config.toml`)
3. Built-in defaults

Invalid TOML, wrong types or ranges, unknown sections/fields, or unsupported
providers produce a clear error before any git or LLM work happens.

---

## Workflow

```bash
# Stage your changes manually
git add src/toolsmith/cli.py

# Generate a commit message
toolsmith cw

# Review the generated message, then choose:
#   a / accept  -> create the commit
#   e / edit    -> open the message in your editor, then accept the edited version
#   r / reject  -> exit without committing

# If you accepted, and push prompting is enabled:
#   y / yes     -> run a normal `git push`
#   <Enter>     -> do not push
```

A normal successful run looks like this:

```text
$ toolsmith cw

Fix staged diff handling for commit writer

Use the cached git diff so commit messages are generated only from
changes the user has already staged.

Proposed commit message:
---
Fix staged diff handling for commit writer

Use the cached git diff so commit messages are generated only from
changes the user has already staged.
---
Accept (a), Edit (e), or Reject (r)? a
Commit created.
Push current branch? [y/N] n
Done.
```

---

## Command options

| Option | Description |
|--------|-------------|
| `--no-push` | Skip the "push current branch?" prompt after a successful commit. |
| `--dry-run` | Generate and display the proposed commit message, then exit. No approval prompt, commit, or push prompt is shown. |
| `--model MODEL` | Override the configured model identifier for this run only. Does not change the provider or local-only policy. |

All options apply only to `toolsmith cw`.

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | Success, or `--dry-run` completed. |
| `1` | General failure. |
| `2` | User rejected or cancelled the operation (including Ctrl+C before commit). |
| `3` | Invalid usage, environment, or configuration. |
| `4` | External dependency failure (git, LLM runtime, editor). |

---

## Troubleshooting

### "Not inside a git repository"

Run `toolsmith cw` from inside a git repository, or initialize one with `git init`.

### "No staged changes found"

Stage at least one change with `git add <file>` before running `toolsmith cw`.

### "Local LLM runtime is unavailable"

Confirm that your Ollama-compatible runtime is running on `localhost:11434` and
that the configured model is available (`ollama list`). Check `timeout_seconds` if
requests time out.

### "LLM returned empty output"

The local model produced no text. Common causes:

- **Reasoning / thinking model.** Some models (for example `qwen3.5:2b` or other
  thinking variants) return their reasoning in a separate `thinking` field and emit
  an empty `response` when the generation budget is consumed before the final
  answer. toolsmith now surfaces a preview of that thinking output in the error.
  Try a non-reasoning coding model such as `qwen2.5-coder:7b`.
- **Incompatible or not fully loaded model.** The model may fail to decode if the
  prompt template does not match. Run:

  ```bash
  ollama logs
  ```

- **Context window too small.** For very large diffs on small models, try lowering
  `max_diff_chars` or increasing the runtime context window.

To inspect the raw response, reproduce the request with `curl`:

```bash
curl -s -X POST http://localhost:11434/api/generate   -H 'Content-Type: application/json'   -d '{"model":"qwen3.5:2b","prompt":"write a short commit message","stream":false,"options":{"temperature":0.2,"num_predict":512}}'   | head -c 500
```

### "No editor found"

`toolsmith cw` resolves `$VISUAL`, then `$EDITOR`, then falls back to `vi`. Set one
of those environment variables, or ensure `vi` is on `PATH`.

### "Commit created, but push failed"

The commit succeeded, but `git push` failed (for example, no upstream configured).
The commit remains in the repository; fix the push issue manually.

### Large diffs

When the staged diff exceeds `max_diff_chars` (default `12000`), the prompt
includes the beginning of the diff followed by a clear truncation marker. The
file summary is always included in full, so rename, delete, and binary context
survives truncation even when the diff text is cut.

---

## Privacy and safety

- **Local-only LLM.** `toolsmith cw` sends the staged diff and file summary only to
the configured local provider on `localhost`. It does not send data to cloud LLM
providers, and it does not silently fall back to one.
- **Staged changes only.** Only `git diff --cached` data is used. Unstaged changes
are never added to the prompt, and working-tree file contents are never opened.
- **No telemetry.** `toolsmith` does not collect usage analytics, crash reports, or
network pings.
- **No automatic staging or code changes.** You must run `git add` yourself.
`toolsmith` never stages, unstages, modifies, or generates code on your behalf.
- **No commit before explicit approval.** The message is always displayed before you
can accept or edit it. Rejecting, cancelling, or any error before approval leaves
the repository uncommitted.
- **No automatic push.** After a successful commit, the push prompt defaults to **no**.
Pressing Enter means no. Only an explicit `y` or `yes` attempts a normal `git push`.
No force flags are used.
- **Dry-run never commits or pushes.** `--dry-run` generates and displays the message,
then exits before any approval, commit, or push prompt.
- **Preserve git hooks and signing.** Commits use `git commit -F <message-file>` with
no hook-bypass or signing-management flags. Your existing hooks and signing
configuration run normally.
- **No diff persistence.** Staged diffs are not written to logs, telemetry, caches, or
durable temporary files. The only temporary file created contains only the proposed
commit message, and it is removed after use.

---

## Development and tests

Run the canonical automated suites. The default run excludes any test that needs a
live LLM provider:

```bash
pytest
pytest tests/unit
pytest tests/integration
```

Install test dependencies first:

```bash
pip install -e ".[dev]"
```

### Optional local-provider smoke test

If you have a running local Ollama-compatible runtime and the configured model:

```bash
pytest -m manual
```

This runs only the excluded manual smoke test. Do not run it in CI without a
runtime, and do not let the test suite download or install models automatically.

### Requirement-to-test traceability

See `tests/TRACEABILITY.md` for the mapping between Phase 8 requirements,
safety invariants, and the tests that validate them.

---

## Limitations and non-goals

Phase 1 intentionally does **not** include:

- Direct `cw` executable alias.
- Conventional Commits mode.
- Regenerate action.
- Non-interactive operation.
- Additional local providers or provider plugin discovery.
- Cloud inference or cloud fallback of any kind.
- Commit-history or repository-wide semantic analysis.
- Automatic stage/unstage, branch creation, code changes, PR creation, issue
  integration, or git configuration/signing management.
- Agent frameworks, autonomous execution, background services, RAG, embeddings,
  vector stores, telemetry, web UI, chat UI, voice UI, or multi-user features.
- Full secret scanning or generated-file classification.
- Email Improver, Error Explainer, Requirements Reviewer, or any command other
  than Commit Writer.

These may be revisited in later phases with updated requirements.

---

## License

MIT
