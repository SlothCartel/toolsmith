"""Shared LLM request/response/client contract (Phase 4)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from toolsmith.errors import DependencyError


@dataclass(frozen=True)
class LLMRequest:
    """Structured request to an LLM client.

    Attributes:
        prompt: The complete prompt text to send to the model.
        model: The model identifier expected by the configured provider.
        temperature: Sampling temperature (0.0-1.0) forwarded to the provider.
        max_tokens: Maximum number of tokens to generate.
        timeout_seconds: Maximum wall-clock time to wait for a response.
    """

    prompt: str
    model: str
    temperature: float
    max_tokens: int
    timeout_seconds: float


@dataclass(frozen=True)
class LLMResponse:
    """Structured response from an LLM client.

    Attributes:
        text: Generated text when ``success`` is True.
        success: Whether the provider produced usable output.
        error: Concise, actionable error message when ``success`` is False.
    """

    text: str
    success: bool
    error: str = ""


@runtime_checkable
class LLMClient(Protocol):
    """Shared LLM client contract consumed by commands.

    Commands depend only on this protocol. Provider adapters implement it.
    """

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send *request* to the provider and return a typed response."""
        ...


def require_success(response: LLMResponse) -> str:
    """Return *response.text* or raise a :class:`DependencyError`.

    This helper keeps provider details out of command orchestration: commands
    receive a typed response and turn a failure response into an actionable
    toolsmith error without leaking transport-level exceptions.
    """
    if response.success:
        return response.text
    raise DependencyError(response.error or "LLM request failed.")
