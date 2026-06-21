"""Tests for the Ollama-compatible local provider adapter.

These tests mock urllib transport so they pass without Ollama, network
access, or a downloaded model.
"""

from __future__ import annotations

import json
import socket
from io import BytesIO
from unittest.mock import MagicMock, patch
from urllib.error import HTTPError, URLError

import pytest

from toolsmith.llm.base import LLMRequest
from toolsmith.llm.ollama import OllamaClient


def _make_request(
    model: str = "qwen2.5-coder:7b",
    temperature: float = 0.2,
    max_tokens: int = 512,
    timeout_seconds: float = 20.0,
) -> LLMRequest:
    return LLMRequest(
        prompt="write a commit message",
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
        timeout_seconds=timeout_seconds,
    )


def _mock_response(payload: dict) -> MagicMock:
    body = json.dumps(payload).encode("utf-8")
    mock = MagicMock()
    mock.__enter__.return_value = mock
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = body
    return mock


def test_valid_response_returns_generated_text():
    client = OllamaClient()
    request = _make_request()
    mock = _mock_response({"response": "Add login validation"})

    with patch("toolsmith.llm.ollama.urlopen", return_value=mock):
        response = client.generate(request)

    assert response.success is True
    assert response.text == "Add login validation"
    assert response.error == ""


def test_request_forwards_model_temperature_max_tokens_and_timeout():
    client = OllamaClient()
    request = _make_request(
        model="llama3.1:latest",
        temperature=0.5,
        max_tokens=256,
        timeout_seconds=30.0,
    )
    mock = _mock_response({"response": "ok"})

    with patch("toolsmith.llm.ollama.urlopen", return_value=mock) as urlopen_mock:
        client.generate(request)

    call_args = urlopen_mock.call_args
    sent_request = call_args.args[0]
    timeout = call_args.kwargs.get("timeout")

    assert sent_request.get_full_url() == "http://localhost:11434/api/generate"
    sent_body = json.loads(sent_request.data)
    assert sent_body["model"] == "llama3.1:latest"
    assert sent_body["prompt"] == "write a commit message"
    assert sent_body["stream"] is False
    assert sent_body["options"]["temperature"] == 0.5
    assert sent_body["options"]["num_predict"] == 256
    assert timeout == 30.0


def test_connection_refused_maps_to_runtime_unavailable():
    client = OllamaClient()
    request = _make_request()
    error = URLError(ConnectionRefusedError(111, "Connection refused"))

    with patch("toolsmith.llm.ollama.urlopen", side_effect=error):
        response = client.generate(request)

    assert response.success is False
    assert "runtime is unavailable" in response.error
    assert "Ollama" in response.error


def test_url_error_with_refused_string_maps_to_runtime_unavailable():
    client = OllamaClient()
    request = _make_request()
    error = URLError("Connection refused")

    with patch("toolsmith.llm.ollama.urlopen", side_effect=error):
        response = client.generate(request)

    assert response.success is False
    assert "runtime is unavailable" in response.error


def test_timeout_error_maps_to_actionable_timeout():
    client = OllamaClient()
    request = _make_request()

    for exception in (socket.timeout, TimeoutError):
        with patch("toolsmith.llm.ollama.urlopen", side_effect=exception()):
            response = client.generate(request)

        assert response.success is False
        assert "timed out" in response.error.lower()


def test_model_not_found_http_404_maps_to_model_unavailable():
    client = OllamaClient()
    request = _make_request(model="missing-model:latest")

    fp = BytesIO(b'{"error": "model not found"}')
    error = HTTPError(
        "http://localhost:11434/api/generate",
        404,
        "Not Found",
        {},
        fp,
    )

    with patch("toolsmith.llm.ollama.urlopen", side_effect=error):
        response = client.generate(request)

    assert response.success is False
    assert "model 'missing-model:latest' is not available" in response.error


def test_other_http_error_includes_status_and_body():
    client = OllamaClient()
    request = _make_request()

    fp = BytesIO(b"internal server error")
    error = HTTPError(
        "http://localhost:11434/api/generate",
        500,
        "Internal Server Error",
        {},
        fp,
    )

    with patch("toolsmith.llm.ollama.urlopen", side_effect=error):
        response = client.generate(request)

    assert response.success is False
    assert "HTTP 500" in response.error
    assert "internal server error" in response.error


def test_malformed_json_maps_to_malformed_response():
    client = OllamaClient()
    request = _make_request()
    mock = MagicMock()
    mock.__enter__.return_value = mock
    mock.__exit__ = MagicMock(return_value=False)
    mock.read.return_value = b"not json"

    with patch("toolsmith.llm.ollama.urlopen", return_value=mock):
        response = client.generate(request)

    assert response.success is False
    assert "malformed response" in response.error


def test_non_object_json_maps_to_malformed_response():
    client = OllamaClient()
    request = _make_request()
    mock = _mock_response(["unexpected list"])

    with patch("toolsmith.llm.ollama.urlopen", return_value=mock):
        response = client.generate(request)

    assert response.success is False
    assert "expected a JSON object" in response.error


def test_missing_response_field_maps_to_malformed_response():
    client = OllamaClient()
    request = _make_request()
    mock = _mock_response({"done": True})

    with patch("toolsmith.llm.ollama.urlopen", return_value=mock):
        response = client.generate(request)

    assert response.success is False
    assert "'response' field is not a string" in response.error


def test_non_string_response_field_maps_to_malformed_response():
    client = OllamaClient()
    request = _make_request()
    mock = _mock_response({"response": 123})

    with patch("toolsmith.llm.ollama.urlopen", return_value=mock):
        response = client.generate(request)

    assert response.success is False
    assert "'response' field is not a string" in response.error


def test_empty_response_text_maps_to_empty_output():
    client = OllamaClient()
    request = _make_request()
    mock = _mock_response({"response": ""})

    with patch("toolsmith.llm.ollama.urlopen", return_value=mock):
        response = client.generate(request)

    assert response.success is False
    assert "empty output" in response.error
