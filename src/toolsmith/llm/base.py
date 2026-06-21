"""Shared LLM request/response/client contract (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class LLMRequest:
    """Structured request to an LLM client."""

    prompt: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)
class LLMResponse:
    """Structured response from an LLM client."""

    text: str
    success: bool
    error: str = ""


class LLMClient(Protocol):
    """Shared LLM client contract consumed by commands."""

    def generate(self, request: LLMRequest) -> LLMResponse:
        ...
