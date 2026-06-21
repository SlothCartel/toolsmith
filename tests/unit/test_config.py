"""Tests for configuration defaults, TOML loading, validation, and precedence."""

from __future__ import annotations

import pytest

from toolsmith import config
from toolsmith.errors import UsageError


def test_defaults_when_user_config_missing(tmp_path):
    cfg = config.build_config(user_config_path=tmp_path / "missing.toml")
    assert cfg.provider == "ollama"
    assert cfg.model == "qwen2.5-coder:7b"
    assert cfg.timeout_seconds == 20
    assert cfg.temperature == 0.2
    assert cfg.max_tokens == 512
    assert cfg.max_diff_chars == 12000
    assert cfg.prompt_push is True


def test_full_user_config_overrides_defaults(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
provider = "ollama"
model = "llama3.1:latest"
timeout_seconds = 30
temperature = 0.5
max_tokens = 256

[commit_writer]
max_diff_chars = 8000
prompt_push = false
"""
    )
    cfg = config.build_config(user_config_path=config_path)
    assert cfg.provider == "ollama"
    assert cfg.model == "llama3.1:latest"
    assert cfg.timeout_seconds == 30
    assert cfg.temperature == 0.5
    assert cfg.max_tokens == 256
    assert cfg.max_diff_chars == 8000
    assert cfg.prompt_push is False


def test_partial_user_config_preserves_other_defaults(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
model = "codellama:latest"
"""
    )
    cfg = config.build_config(user_config_path=config_path)
    assert cfg.model == "codellama:latest"
    assert cfg.provider == "ollama"
    assert cfg.timeout_seconds == 20
    assert cfg.temperature == 0.2
    assert cfg.max_tokens == 512
    assert cfg.max_diff_chars == 12000
    assert cfg.prompt_push is True


def test_cli_model_override_beats_user_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
model = "user-model:latest"
"""
    )
    cfg = config.build_config(
        cli_overrides={"model": "cli-model:latest"},
        user_config_path=config_path,
    )
    assert cfg.model == "cli-model:latest"


def test_cli_no_push_override_beats_user_config(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[commit_writer]
prompt_push = true
"""
    )
    cfg = config.build_config(
        cli_overrides={"no_push": True},
        user_config_path=config_path,
    )
    assert cfg.prompt_push is False


def test_cli_model_without_user_config_uses_defaults(tmp_path):
    cfg = config.build_config(
        cli_overrides={"model": "mistral:latest"},
        user_config_path=tmp_path / "missing.toml",
    )
    assert cfg.model == "mistral:latest"
    assert cfg.provider == "ollama"


def test_invalid_toml_raises_usage_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text("[[invalid toml")
    with pytest.raises(UsageError) as exc_info:
        config.build_config(user_config_path=config_path)
    assert exc_info.value.exit_code == 3
    assert "Invalid TOML" in str(exc_info.value)


def test_unsupported_provider_raises_usage_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
provider = "openai"
"""
    )
    with pytest.raises(UsageError) as exc_info:
        config.build_config(user_config_path=config_path)
    assert "Unsupported LLM provider" in str(exc_info.value)
    assert "openai" in str(exc_info.value)


def test_wrong_type_for_temperature_raises_usage_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
temperature = "low"
"""
    )
    with pytest.raises(UsageError) as exc_info:
        config.build_config(user_config_path=config_path)
    assert "llm.temperature" in str(exc_info.value)


def test_temperature_out_of_range_raises_usage_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
temperature = 1.5
"""
    )
    with pytest.raises(UsageError) as exc_info:
        config.build_config(user_config_path=config_path)
    assert "between 0 and 1" in str(exc_info.value)


def test_non_positive_timeout_raises_usage_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
timeout_seconds = 0
"""
    )
    with pytest.raises(UsageError) as exc_info:
        config.build_config(user_config_path=config_path)
    assert "positive number" in str(exc_info.value)


def test_non_positive_max_diff_chars_raises_usage_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[commit_writer]
max_diff_chars = -100
"""
    )
    with pytest.raises(UsageError) as exc_info:
        config.build_config(user_config_path=config_path)
    assert "positive integer" in str(exc_info.value)


def test_unknown_top_level_section_raises_usage_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[unknown]
key = "value"
"""
    )
    with pytest.raises(UsageError) as exc_info:
        config.build_config(user_config_path=config_path)
    assert "Unknown config section" in str(exc_info.value)


def test_unknown_llm_field_raises_usage_error(tmp_path):
    config_path = tmp_path / "config.toml"
    config_path.write_text(
        """
[llm]
secret = "value"
"""
    )
    with pytest.raises(UsageError) as exc_info:
        config.build_config(user_config_path=config_path)
    assert "[llm].secret" in str(exc_info.value)
