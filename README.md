# toolsmith

A lightweight, modular, local-first command-line productivity assistant for developers.

Phase 1 focuses on the **Commit Writer** command (`toolsmith cw`). At this stage only the repository governance and the smallest installable Python package scaffold are in place; the actual Commit Writer behavior is intentionally not implemented yet.

## Project status

- `toolsmith --help` works and shows the root help.
- `toolsmith cw` is registered as a placeholder; it does not read git state, call an LLM, create commits, or push.
- All planned package subdirectories exist and are importable.
- Automated tests run with `pytest`.

## Development

Install in editable mode with test dependencies:

```bash
pip install -e ".[dev]"
```

Run the canonical automated test suites. The default run excludes any test that
needs a live LLM provider:

```bash
pytest
pytest tests/unit
pytest tests/integration
```

### Optional local-provider smoke test

If you have a running local Ollama-compatible runtime and the configured model,
you can run the excluded manual smoke test:

```bash
pytest -m manual
```

Do not run the manual tests in CI without a runtime, and do not let the test suite
download or install models automatically.

### Requirement-to-test traceability

See `tests/TRACEABILITY.md` for the mapping between Phase 8 requirements,
safety invariants, and the tests that validate them.

### Performance notes

- `toolsmith --help` is smoke-tested to start in well under 2 seconds on warm hardware.
- Prompt size is structurally bounded by the configured `max_diff_chars` plus a small
  fixed instruction overhead; see `tests/unit/test_commit_writer_prompt.py`.
- Actual LLM generation times depend heavily on hardware, model, and load. Treat any
  "warm runtime under 3 s / 8 s" targets as manual benchmarks, not deterministic CI
  assertions.

## Architecture

See `agents/AGENTS.md` for the architecture map, module responsibilities, stack decisions, and update triggers. See `agents/GUARDRAILS.md` for the Phase 1 safety and scope invariants.

## Requirements

- Python 3.10+
- pytest for running tests

## License

MIT
