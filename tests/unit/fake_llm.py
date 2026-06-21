"""Fake LLM client test utility for unit tests."""

from __future__ import annotations

from toolsmith.llm.base import LLMClient, LLMRequest, LLMResponse


class FakeLLMClient(LLMClient):
    """In-memory LLM client that records requests and returns a fixed response.

    This utility lets command tests inject a deterministic provider without
    importing the real Ollama adapter or making network calls.
    """

    def __init__(self, response: LLMResponse | None = None) -> None:
        self.response = response or LLMResponse(
            text="fake generated commit message", success=True
        )
        self.calls: list[LLMRequest] = []

    def generate(self, request: LLMRequest) -> LLMResponse:
        self.calls.append(request)
        return self.response
