"""Ollama-compatible local provider adapter (Phase 4)."""

from __future__ import annotations

from toolsmith.llm.base import LLMClient, LLMRequest, LLMResponse


class OllamaClient(LLMClient):
    """Local Ollama-compatible adapter; behavior is deferred to Phase 4."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        raise NotImplementedError("Ollama adapter is not implemented in Phase 1.")
