"""Configuration defaults and loader (Phase 2+)."""

from __future__ import annotations

DEFAULTS: dict[str, object] = {
    "llm": {
        "provider": "ollama",
        "model": "qwen2.5-coder:7b",
        "timeout_seconds": 20,
        "temperature": 0.2,
    },
    "commit_writer": {
        "max_diff_chars": 12000,
        "prompt_push": True,
    },
}
