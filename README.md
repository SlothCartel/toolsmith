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

Run tests:

```bash
pytest
pytest tests/unit
pytest tests/integration
```

## Architecture

See `agents/AGENTS.md` for the architecture map, module responsibilities, stack decisions, and update triggers. See `agents/GUARDRAILS.md` for the Phase 1 safety and scope invariants.

## Requirements

- Python 3.10+
- pytest for running tests

## License

MIT
