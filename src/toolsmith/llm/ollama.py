"""Ollama-compatible local provider adapter (Phase 4)."""

from __future__ import annotations

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from toolsmith.llm.base import LLMClient, LLMRequest, LLMResponse

DEFAULT_OLLAMA_URL = "http://localhost:11434/api/generate"


class OllamaClient(LLMClient):
    """Local Ollama-compatible adapter using the Ollama generate API.

    This adapter is intentionally local-only: it targets the default Ollama
    endpoint on ``localhost`` and never sends data to a remote service.
    """

    def __init__(self, base_url: str = DEFAULT_OLLAMA_URL) -> None:
        self.base_url = base_url

    def generate(self, request: LLMRequest) -> LLMResponse:
        """Send a generate request to the local Ollama runtime.

        Maps connection failures, missing models, timeouts, malformed
        payloads, and empty output to actionable, provider-agnostic responses.
        """
        payload = {
            "model": request.model,
            "prompt": request.prompt,
            "stream": False,
            "options": {
                "temperature": request.temperature,
                "num_predict": request.max_tokens,
            },
        }
        data = json.dumps(payload).encode("utf-8")
        req = Request(
            self.base_url,
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(req, timeout=request.timeout_seconds) as response:
                raw = response.read()
        except HTTPError as exc:
            return _map_http_error(exc, request.model)
        except URLError as exc:
            return _map_url_error(exc)
        except (socket.timeout, TimeoutError):
            return LLMResponse(
                text="",
                success=False,
                error="Local LLM request timed out. Check timeout_seconds or confirm the runtime is responding.",
            )

        return _parse_ollama_response(raw)


def _map_http_error(exc: HTTPError, model: str) -> LLMResponse:
    """Map an Ollama HTTP error to an actionable response."""
    body = exc.read()
    body_text = body.decode("utf-8", errors="replace")[:200]

    if exc.code == 404:
        return LLMResponse(
            text="",
            success=False,
            error=f"Local LLM model {model!r} is not available. Check `ollama list` and pull the model if needed.",
        )

    return LLMResponse(
        text="",
        success=False,
        error=f"Local LLM runtime returned HTTP {exc.code}: {body_text}",
    )


def _map_url_error(exc: URLError) -> LLMResponse:
    """Map a transport-level URL error to an actionable response."""
    reason = exc.reason
    if isinstance(reason, ConnectionRefusedError) or (
        isinstance(reason, str) and "refused" in reason.lower()
    ):
        return LLMResponse(
            text="",
            success=False,
            error="Local LLM runtime is unavailable. Check that Ollama is running on localhost:11434.",
        )

    reason_text = str(reason)
    return LLMResponse(
        text="",
        success=False,
        error=f"Could not reach local LLM runtime: {reason_text}",
    )


def _parse_ollama_response(raw: bytes) -> LLMResponse:
    """Parse a successful Ollama JSON response and validate output."""
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        return LLMResponse(
            text="",
            success=False,
            error=f"LLM returned malformed response: {exc}",
        )

    try:
        response_json = json.loads(text)
    except json.JSONDecodeError as exc:
        return LLMResponse(
            text="",
            success=False,
            error=f"LLM returned malformed response: {exc}",
        )

    if not isinstance(response_json, dict):
        return LLMResponse(
            text="",
            success=False,
            error="LLM returned malformed response: expected a JSON object.",
        )

    generated = response_json.get("response")
    if not isinstance(generated, str):
        return LLMResponse(
            text="",
            success=False,
            error="LLM returned malformed response: 'response' field is not a string.",
        )

    if generated == "":
        return LLMResponse(
            text="",
            success=False,
            error="LLM returned empty output.",
        )

    return LLMResponse(text=generated, success=True)
