"""Tests for terminal accept/edit/reject prompts."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from toolsmith.errors import CancelError
from toolsmith.ui.prompts import prompt_accept_edit_reject, prompt_push


MESSAGE = "Fix detection\n\nUse cached diff."


class TestPromptAcceptEditReject:
    def test_displays_message_before_prompt(self, capsys):
        with patch("builtins.input", side_effect=["a"]):
            prompt_accept_edit_reject(MESSAGE)

        captured = capsys.readouterr()
        assert "Proposed commit message:" in captured.out
        assert MESSAGE in captured.out
        assert "---" in captured.out

    def test_accept_shortcut(self):
        with patch("builtins.input", side_effect=["a"]):
            assert prompt_accept_edit_reject(MESSAGE) == "accept"

    def test_accept_full_word(self):
        with patch("builtins.input", side_effect=["accept"]):
            assert prompt_accept_edit_reject(MESSAGE) == "accept"

    def test_edit_shortcut(self):
        with patch("builtins.input", side_effect=["e"]):
            assert prompt_accept_edit_reject(MESSAGE) == "edit"

    def test_edit_full_word(self):
        with patch("builtins.input", side_effect=["edit"]):
            assert prompt_accept_edit_reject(MESSAGE) == "edit"

    def test_reject_shortcut_raises_cancel(self):
        with patch("builtins.input", side_effect=["r"]), pytest.raises(CancelError) as exc_info:
            prompt_accept_edit_reject(MESSAGE)
        assert "rejected" in str(exc_info.value).lower()
        assert "no commit" in str(exc_info.value).lower()

    def test_reject_full_word_raises_cancel(self):
        with patch("builtins.input", side_effect=["reject"]), pytest.raises(CancelError):
            prompt_accept_edit_reject(MESSAGE)

    def test_blank_input_reprompts(self):
        with patch("builtins.input", side_effect=["", "", "a"]):
            assert prompt_accept_edit_reject(MESSAGE) == "accept"

    def test_invalid_input_reprompts(self):
        with patch("builtins.input", side_effect=["maybe", "x", "a"]):
            assert prompt_accept_edit_reject(MESSAGE) == "accept"

    def test_case_insensitive_input(self):
        with patch("builtins.input", side_effect=["A"]):
            assert prompt_accept_edit_reject(MESSAGE) == "accept"
        with patch("builtins.input", side_effect=["E"]):
            assert prompt_accept_edit_reject(MESSAGE) == "edit"
        with patch("builtins.input", side_effect=["R"]):
            with pytest.raises(CancelError):
                prompt_accept_edit_reject(MESSAGE)

    def test_whitespace_input_is_blank(self):
        with patch("builtins.input", side_effect=["   ", "a"]):
            assert prompt_accept_edit_reject(MESSAGE) == "accept"

    def test_eof_raises_cancel(self):
        with patch("builtins.input", side_effect=EOFError()), pytest.raises(CancelError) as exc_info:
            prompt_accept_edit_reject(MESSAGE)
        assert "no commit" in str(exc_info.value).lower()

    def test_keyboard_interrupt_propagates(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt()), pytest.raises(KeyboardInterrupt):
            prompt_accept_edit_reject(MESSAGE)

    def test_reject_prints_invalid_message_on_bad_input(self, capsys):
        with patch("builtins.input", side_effect=["nope", "a"]):
            prompt_accept_edit_reject(MESSAGE)
        captured = capsys.readouterr()
        assert "Invalid choice" in captured.out


class TestPromptPush:
    def test_explicit_yes_returns_true(self):
        with patch("builtins.input", return_value="y"):
            assert prompt_push() is True

    def test_explicit_yes_full_word(self):
        with patch("builtins.input", return_value="yes"):
            assert prompt_push() is True

    def test_blank_returns_false(self):
        with patch("builtins.input", return_value=""):
            assert prompt_push() is False

    def test_no_returns_false(self):
        with patch("builtins.input", return_value="n"):
            assert prompt_push() is False

    def test_any_other_input_returns_false(self):
        with patch("builtins.input", return_value="maybe"):
            assert prompt_push() is False

    def test_case_insensitive_yes(self):
        with patch("builtins.input", return_value="Y"):
            assert prompt_push() is True

    def test_keyboard_interrupt_returns_false(self):
        with patch("builtins.input", side_effect=KeyboardInterrupt()):
            assert prompt_push() is False

    def test_eof_returns_false(self):
        with patch("builtins.input", side_effect=EOFError()):
            assert prompt_push() is False
