"""Smoke tests proving all planned modules are importable."""

from __future__ import annotations


def test_import_root_package():
    import toolsmith

    assert toolsmith.__version__


def test_import_cli():
    from toolsmith import cli

    assert cli.main is not None
    assert cli.create_parser is not None


def test_import_config():
    from toolsmith import config

    assert config.DEFAULTS


def test_import_errors():
    from toolsmith import errors

    assert errors.ToolsmithError is not None


def test_import_commands():
    from toolsmith.commands import commit_writer

    assert commit_writer.run is not None


def test_import_git_modules():
    from toolsmith.git import repository, diff, commit

    assert repository is not None
    assert diff is not None
    assert commit is not None


def test_import_llm_modules():
    from toolsmith.llm import base, ollama

    assert base.LLMRequest is not None
    assert base.LLMResponse is not None
    assert base.LLMClient is not None
    assert ollama.OllamaClient is not None


def test_import_prompts():
    from toolsmith.prompts import commit_writer

    assert commit_writer is not None


def test_import_ui_modules():
    from toolsmith.ui import prompts, editor

    assert prompts is not None
    assert editor is not None
