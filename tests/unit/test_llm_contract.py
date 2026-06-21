"""Tests for the shared LLM request/response/client contract."""

from __future__ import annotations

import pytest

from toolsmith.errors import DependencyError
from toolsmith.llm import create_client
from toolsmith.llm.base import LLMClient, LLMRequest, LLMResponse, require_success
from toolsmith.llm.ollama import OllamaClient
from .fake_llm import FakeLLMClient


def test_llm_request_carries_expected_fields():
    request = LLMRequest(
        prompt="summarize these changes",
        model="qwen2.5-coder:7b",
        temperature=0.2,
        max_tokens=512,
        timeout_seconds=20.0,
    )
    assert request.prompt == "summarize these changes"
    assert request.model == "qwen2.5-coder:7b"
    assert request.temperature == 0.2
    assert request.max_tokens == 512
    assert request.timeout_seconds == 20.0


def test_llm_response_success_has_text_and_no_error():
    response = LLMResponse(text="generated message", success=True)
    assert response.text == "generated message"
    assert response.success is True
    assert response.error == ""


def test_llm_response_failure_has_actionable_error():
    response = LLMResponse(
        text="",
        success=False,
        error="Local LLM runtime is unavailable.",
    )
    assert response.text == ""
    assert response.success is False
    assert "unavailable" in response.error


def test_llm_client_is_runtime_checkable_protocol():
    assert isinstance(FakeLLMClient(), LLMClient)
    assert isinstance(OllamaClient(), LLMClient)


def test_fake_client_records_requests_and_returns_fixed_response():
    client = FakeLLMClient()
    request = LLMRequest(
        prompt="p",
        model="m",
        temperature=0.0,
        max_tokens=10,
        timeout_seconds=1.0,
    )
    response = client.generate(request)
    assert response.success is True
    assert response.text == "fake generated commit message"
    assert client.calls == [request]


def test_fake_client_can_return_failure_response():
    client = FakeLLMClient(
        response=LLMResponse(text="", success=False, error="mock failure")
    )
    request = LLMRequest(
        prompt="p",
        model="m",
        temperature=0.0,
        max_tokens=10,
        timeout_seconds=1.0,
    )
    response = client.generate(request)
    assert response.success is False
    assert response.error == "mock failure"
    assert client.calls == [request]


def test_require_success_returns_text_on_success():
    response = LLMResponse(text="ok", success=True)
    assert require_success(response) == "ok"


def test_require_success_raises_dependency_error_on_failure():
    response = LLMResponse(
        text="",
        success=False,
        error="Local LLM runtime is unavailable.",
    )
    with pytest.raises(DependencyError) as exc_info:
        require_success(response)
    assert exc_info.value.exit_code == 4
    assert "unavailable" in str(exc_info.value)


def test_require_success_raises_dependency_error_for_blank_error():
    response = LLMResponse(text="", success=False)
    with pytest.raises(DependencyError) as exc_info:
        require_success(response)
    assert "LLM request failed" in str(exc_info.value)


def test_create_client_returns_ollama_client_for_supported_provider():
    client = create_client("ollama")
    assert isinstance(client, OllamaClient)


def test_create_client_rejects_unsupported_provider():
    from toolsmith.errors import UsageError

    with pytest.raises(UsageError) as exc_info:
        create_client("openai")
    assert exc_info.value.exit_code == 3
    assert "Unsupported LLM provider" in str(exc_info.value)
    assert "openai" in str(exc_info.value)
