"""Tests for the placeholder CLI."""

from __future__ import annotations

import pytest

from toolsmith.cli import create_parser, main


def test_root_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        create_parser().parse_args(["--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "toolsmith" in captured.out
    assert "cw" in captured.out


def test_cw_help(capsys):
    with pytest.raises(SystemExit) as exc_info:
        create_parser().parse_args(["cw", "--help"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "Commit Writer" in captured.out


def test_main_no_args_prints_help(capsys):
    code = main([])
    assert code == 0
    captured = capsys.readouterr()
    assert "toolsmith" in captured.out
    assert "cw" in captured.out


def test_main_cw_placeholder(capsys):
    code = main(["cw"])
    assert code == 0
    captured = capsys.readouterr()
    assert "not implemented in Phase 1" in captured.out


def test_main_version(capsys):
    with pytest.raises(SystemExit) as exc_info:
        main(["--version"])

    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    assert "toolsmith" in captured.out
