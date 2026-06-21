"""toolsmith LLM boundary modules."""

from __future__ import annotations

from toolsmith.errors import UsageError
from toolsmith.llm.base import LLMClient, LLMRequest, LLMResponse, require_success
from toolsmith.llm.ollama import OllamaClient

SUPPORTED_PROVIDERS = frozenset({"ollama"})


def create_client(provider: str) -> LLMClient:
    """Create a local LLM client for the configured provider.

    Phase 4 supports only the local Ollama-compatible provider. Config-time
    validation already rejects unsupported values; this factory is the final
    runtime guard so commands never instantiate an unsupported provider.
    """
    if provider == "ollama":
        return OllamaClient()

    supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
    raise UsageError(
        f"Unsupported LLM provider {provider!r}. Supported providers: {supported}."
    )
