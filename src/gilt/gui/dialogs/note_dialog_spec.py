from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from gilt.gui.dialogs.note_dialog import NoteDialog

    HAS_QT = True
except ImportError:
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


class DescribeNoteDialog:
    def it_should_prepopulate_with_existing_note(self):
        dialog = NoteDialog(current_note="existing note")
        assert dialog.note_edit.toPlainText() == "existing note"

    def it_should_start_empty_when_no_note_provided(self):
        dialog = NoteDialog()
        assert dialog.note_edit.toPlainText() == ""

    def it_should_return_trimmed_note_from_get_note(self):
        dialog = NoteDialog(current_note="  padded  ")
        assert dialog.get_note() == "padded"

    def it_should_return_empty_string_when_note_is_whitespace_only(self):
        dialog = NoteDialog(current_note="   ")
        assert dialog.get_note() == ""

    def it_should_set_window_title_to_edit_note(self):
        dialog = NoteDialog()
        assert dialog.windowTitle() == "Edit Note"

    def it_should_reflect_updated_text_in_get_note(self):
        dialog = NoteDialog(current_note="original")
        dialog.note_edit.setPlainText("updated note")
        assert dialog.get_note() == "updated note"
