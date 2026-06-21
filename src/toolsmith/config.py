"""Configuration defaults, TOML loading, validation, and precedence."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ModuleNotFoundError:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib

from toolsmith.errors import UsageError


DEFAULT_PROVIDER = "ollama"
DEFAULT_MODEL = "qwen2.5-coder:7b"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_TEMPERATURE = 0.2
DEFAULT_MAX_TOKENS = 512
DEFAULT_MAX_DIFF_CHARS = 12000
DEFAULT_PROMPT_PUSH = True

DEFAULTS: dict[str, dict[str, object]] = {
    "llm": {
        "provider": DEFAULT_PROVIDER,
        "model": DEFAULT_MODEL,
        "timeout_seconds": DEFAULT_TIMEOUT_SECONDS,
        "temperature": DEFAULT_TEMPERATURE,
        "max_tokens": DEFAULT_MAX_TOKENS,
    },
    "commit_writer": {
        "max_diff_chars": DEFAULT_MAX_DIFF_CHARS,
        "prompt_push": DEFAULT_PROMPT_PUSH,
    },
}

SUPPORTED_PROVIDERS = frozenset({DEFAULT_PROVIDER})

_KNOWN_LLM_FIELDS = frozenset(DEFAULTS["llm"].keys())
_KNOWN_COMMIT_WRITER_FIELDS = frozenset(DEFAULTS["commit_writer"].keys())


@dataclass(frozen=True)
class Config:
    """Validated runtime configuration for toolsmith."""

    provider: str
    model: str
    timeout_seconds: float
    temperature: float
    max_tokens: int
    max_diff_chars: int
    prompt_push: bool


def _get_config_path() -> Path:
    """Default user configuration path."""
    return Path.home() / ".config" / "toolsmith" / "config.toml"


def _load_raw_config(path: Path | None = None) -> dict[str, Any]:
    """Load the optional user TOML file, returning an empty dict when absent."""
    config_path = path or _get_config_path()
    if not config_path.exists():
        return {}
    try:
        with config_path.open("rb") as handle:
            return tomllib.load(handle)
    except tomllib.TOMLDecodeError as exc:
        raise UsageError(
            f"Invalid TOML in config file {config_path}: {exc}"
        ) from None


def _require_type(field: str, value: Any, *expected: type) -> Any:
    """Validate that *value* has one of the expected types."""
    if not isinstance(value, expected):
        type_names = " or ".join(t.__name__ for t in expected)
        raise UsageError(
            f"Config field {field!r} must be {type_names}, got {type(value).__name__}."
        )
    return value


def _require_string(field: str, value: Any) -> str:
    """Validate a non-empty string config value."""
    value = _require_type(field, value, str)
    if not value.strip():
        raise UsageError(f"Config field {field!r} must be a non-empty string.")
    return value


def _require_positive_number(field: str, value: Any) -> float:
    """Validate a positive numeric config value."""
    value = _require_type(field, value, int, float)
    if value <= 0 or math.isinf(value) or math.isnan(value):
        raise UsageError(f"Config field {field!r} must be a positive number, got {value}.")
    return float(value)


def _require_temperature(field: str, value: Any) -> float:
    """Validate a temperature value between 0 and 1."""
    value = _require_type(field, value, int, float)
    if not 0 <= value <= 1:
        raise UsageError(
            f"Config field {field!r} must be between 0 and 1, got {value}."
        )
    return float(value)


def _require_positive_int(field: str, value: Any) -> int:
    """Validate a positive integer config value."""
    value = _require_type(field, value, int)
    if value <= 0:
        raise UsageError(f"Config field {field!r} must be a positive integer, got {value}.")
    return value


def _require_bool(field: str, value: Any) -> bool:
    """Validate a boolean config value."""
    return _require_type(field, value, bool)


def _validate_config(raw: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Merge *raw* user config with defaults and enforce schema/range rules."""
    if not isinstance(raw, dict):
        raise UsageError("Config file must contain a TOML table at the top level.")

    for key in raw:
        if key not in DEFAULTS:
            raise UsageError(f"Unknown config section {key!r}.")

    llm: dict[str, Any] = dict(DEFAULTS["llm"])
    commit_writer: dict[str, Any] = dict(DEFAULTS["commit_writer"])

    raw_llm = raw.get("llm")
    if raw_llm is not None:
        if not isinstance(raw_llm, dict):
            raise UsageError("Config section [llm] must be a table.")
        for key in raw_llm:
            if key not in _KNOWN_LLM_FIELDS:
                raise UsageError(f"Unknown config field [llm].{key}.")
        llm.update(raw_llm)

    raw_cw = raw.get("commit_writer")
    if raw_cw is not None:
        if not isinstance(raw_cw, dict):
            raise UsageError("Config section [commit_writer] must be a table.")
        for key in raw_cw:
            if key not in _KNOWN_COMMIT_WRITER_FIELDS:
                raise UsageError(f"Unknown config field [commit_writer].{key}.")
        commit_writer.update(raw_cw)

    provider = _require_string("llm.provider", llm["provider"])
    if provider not in SUPPORTED_PROVIDERS:
        supported = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise UsageError(
            f"Unsupported LLM provider {provider!r}. Supported providers: {supported}."
        )

    return {
        "llm": {
            "provider": provider,
            "model": _require_string("llm.model", llm["model"]),
            "timeout_seconds": _require_positive_number(
                "llm.timeout_seconds", llm["timeout_seconds"]
            ),
            "temperature": _require_temperature("llm.temperature", llm["temperature"]),
            "max_tokens": _require_positive_int("llm.max_tokens", llm["max_tokens"]),
        },
        "commit_writer": {
            "max_diff_chars": _require_positive_int(
                "commit_writer.max_diff_chars", commit_writer["max_diff_chars"]
            ),
            "prompt_push": _require_bool(
                "commit_writer.prompt_push", commit_writer["prompt_push"]
            ),
        },
    }


def build_config(
    *,
    cli_overrides: dict[str, Any] | None = None,
    user_config_path: Path | None = None,
) -> Config:
    """Build a validated :class:`Config` from defaults, user TOML, and CLI overrides.

    Precedence: CLI override > user config > built-in defaults.
    """
    raw = _load_raw_config(user_config_path)
    merged = _validate_config(raw)

    llm = dict(merged["llm"])
    commit_writer = dict(merged["commit_writer"])

    if cli_overrides:
        if cli_overrides.get("model") is not None:
            llm["model"] = _require_string("cli --model", cli_overrides["model"])
        if cli_overrides.get("no_push") is not None:
            commit_writer["prompt_push"] = not cli_overrides["no_push"]

    return Config(
        provider=llm["provider"],
        model=llm["model"],
        timeout_seconds=llm["timeout_seconds"],
        temperature=llm["temperature"],
        max_tokens=llm["max_tokens"],
        max_diff_chars=commit_writer["max_diff_chars"],
        prompt_push=commit_writer["prompt_push"],
    )
