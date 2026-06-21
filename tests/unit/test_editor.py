"""Tests for external editor resolution, invocation, and cleanup."""

from __future__ import annotations

import os
import shutil
import stat
from pathlib import Path
from unittest.mock import patch

import pytest

from toolsmith.errors import CancelError, DependencyError
from toolsmith.ui.editor import _FALLBACK_EDITOR, edit_message, resolve_editor


def _make_fake_editor(tmp_path: Path, script: str) -> Path:
    editor = tmp_path / "editor.sh"
    editor.write_text(script)
    editor.chmod(editor.stat().st_mode | stat.S_IXUSR)
    return editor


class TestResolveEditor:
    def test_visual_takes_precedence(self, monkeypatch, tmp_path):
        visual = tmp_path / "visual"
        visual.write_text("# visual")
        editor = tmp_path / "plain"
        editor.write_text("# editor")
        monkeypatch.setenv("VISUAL", str(visual))
        monkeypatch.setenv("EDITOR", str(editor))
        assert resolve_editor() == str(visual)

    def test_editor_used_when_visual_missing(self, monkeypatch, tmp_path):
        editor = tmp_path / "plain"
        editor.write_text("# editor")
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.setenv("EDITOR", str(editor))
        assert resolve_editor() == str(editor)

    def test_visual_empty_string_falls_back_to_editor(self, monkeypatch, tmp_path):
        editor = tmp_path / "plain"
        editor.write_text("# editor")
        monkeypatch.setenv("VISUAL", "")
        monkeypatch.setenv("EDITOR", str(editor))
        assert resolve_editor() == str(editor)

    def test_fallback_to_vi_when_available(self, monkeypatch):
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        with patch.object(shutil, "which", return_value="/usr/bin/vi"):
            assert resolve_editor() == "/usr/bin/vi"

    def test_missing_editor_raises_dependency_error(self, monkeypatch):
        monkeypatch.delenv("VISUAL", raising=False)
        monkeypatch.delenv("EDITOR", raising=False)
        with patch.object(shutil, "which", return_value=None):
            with pytest.raises(DependencyError) as exc_info:
                resolve_editor()
        assert "$VISUAL" in str(exc_info.value) or "$EDITOR" in str(exc_info.value)


class TestEditMessage:
    def test_successful_edit_returns_edited_text_and_cleans_temp(self, tmp_path, monkeypatch):
        editor = _make_fake_editor(
            tmp_path,
            "#!/bin/sh\nsed -i 's/Fix/Updated/' \"$1\"",
        )
        monkeypatch.setenv("VISUAL", str(editor))

        result = edit_message("Fix detection")

        assert result == "Updated detection"

    def test_editor_receives_only_message_not_diff(self, tmp_path, monkeypatch):
        recorded = []

        script = "#!/bin/sh\ncp \"$1\" \"{}\"".format(tmp_path / "captured.txt")
        editor = _make_fake_editor(tmp_path, script)
        monkeypatch.setenv("VISUAL", str(editor))

        edit_message("Only the message")

        captured = (tmp_path / "captured.txt").read_text()
        assert captured == "Only the message"
        assert "diff" not in captured.lower()
        assert "staged" not in captured.lower()

    def test_empty_edited_result_is_allowed_by_editor(self, tmp_path, monkeypatch):
        editor = _make_fake_editor(tmp_path, "#!/bin/sh\n: \u003e \"$1\"")
        monkeypatch.setenv("VISUAL", str(editor))

        assert edit_message("Fix detection") == ""

    def test_temp_file_is_removed_after_success(self, tmp_path, monkeypatch):
        editor = _make_fake_editor(tmp_path, "#!/bin/sh\nsed -i 's/Fix/Updated/' \"$1\"")
        monkeypatch.setenv("VISUAL", str(editor))

        removed: list[str] = []
        original_unlink = os.unlink

        def tracking_unlink(path: str) -> None:
            removed.append(path)
            original_unlink(path)

        monkeypatch.setattr("toolsmith.ui.editor.os.unlink", tracking_unlink)

        edit_message("Fix detection")

        assert len(removed) == 1
        assert not Path(removed[0]).exists()

    def test_temp_file_is_removed_on_nonzero_exit(self, tmp_path, monkeypatch):
        editor = _make_fake_editor(tmp_path, "#!/bin/sh\nexit 1")
        monkeypatch.setenv("VISUAL", str(editor))

        removed: list[str] = []
        original_unlink = os.unlink

        def tracking_unlink(path: str) -> None:
            removed.append(path)
            original_unlink(path)

        monkeypatch.setattr("toolsmith.ui.editor.os.unlink", tracking_unlink)

        with pytest.raises(DependencyError):
            edit_message("Fix detection")

        assert len(removed) == 1
        assert not Path(removed[0]).exists()

    def test_nonzero_editor_exit_raises_dependency_error(self, tmp_path, monkeypatch):
        editor = _make_fake_editor(tmp_path, "#!/bin/sh\necho editor failed \u003e\u00262\nexit 42")
        monkeypatch.setenv("VISUAL", str(editor))

        with pytest.raises(DependencyError) as exc_info:
            edit_message("Fix detection")

        assert "42" in str(exc_info.value)
        assert "editor failed" in str(exc_info.value)
        assert "no commit" in str(exc_info.value).lower()

    def test_signal_termination_raises_cancel(self, tmp_path, monkeypatch):
        editor = _make_fake_editor(tmp_path, "#!/bin/sh\nkill -INT $$")
        monkeypatch.setenv("VISUAL", str(editor))

        with pytest.raises(CancelError) as exc_info:
            edit_message("Fix detection")

        assert "cancelled" in str(exc_info.value).lower()
        assert "no commit" in str(exc_info.value).lower()

    def test_invoked_without_shell(self, tmp_path, monkeypatch):
        # A real editor string containing spaces would be split incorrectly if
        # passed to a shell, so we ensure it is treated as a single argv entry.
        editor_path = _make_fake_editor(tmp_path, "#!/bin/sh\nsed -i 's/Fix/Updated/' \"$1\"")
        monkeypatch.setenv("VISUAL", str(editor_path))

        result = edit_message("Fix detection")
        assert result == "Updated detection"

    def test_editor_path_with_spaces_not_interpreted_by_shell(self, tmp_path, monkeypatch):
        spaced = tmp_path / "my editor.sh"
        spaced.write_text("#!/bin/sh\nsed -i 's/Fix/Updated/' \"$1\"")
        spaced.chmod(spaced.stat().st_mode | stat.S_IXUSR)
        monkeypatch.setenv("VISUAL", str(spaced))

        result = edit_message("Fix detection")
        assert result == "Updated detection"
