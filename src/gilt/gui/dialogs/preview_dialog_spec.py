from __future__ import annotations

import pytest

try:
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from gilt.gui.dialogs.preview_dialog import PreviewDialog

    HAS_QT = True
except ImportError:
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


class DescribePreviewDialog:
    def it_should_add_row_with_correct_cell_values(self):
        dialog = PreviewDialog("Title", "Do something", ["Col A", "Col B"])
        dialog.add_row(["val1", "val2"])
        assert dialog.table.rowCount() == 1
        assert dialog.table.item(0, 0).text() == "val1"
        assert dialog.table.item(0, 1).text() == "val2"

    def it_should_raise_when_values_count_mismatches_columns(self):
        dialog = PreviewDialog("Title", "Do something", ["Col A", "Col B"])
        with pytest.raises(ValueError):
            dialog.add_row(["only_one"])

    def it_should_accumulate_multiple_rows(self):
        dialog = PreviewDialog("Title", "Do something", ["Col A"])
        dialog.add_row(["first"])
        dialog.add_row(["second"])
        assert dialog.table.rowCount() == 2

    def it_should_clear_all_rows(self):
        dialog = PreviewDialog("Title", "Do something", ["Col A"])
        dialog.add_row(["value"])
        dialog.clear_rows()
        assert dialog.table.rowCount() == 0

    def it_should_start_with_apply_button_disabled(self):
        dialog = PreviewDialog("Title", "Do something", ["Col A"])
        assert not dialog.apply_btn.isEnabled()

    def it_should_enable_apply_button_when_confirm_checked(self):
        dialog = PreviewDialog("Title", "Do something", ["Col A"])
        dialog.confirm_check.setChecked(True)
        assert dialog.apply_btn.isEnabled()

    def it_should_disable_apply_button_when_confirm_unchecked(self):
        dialog = PreviewDialog("Title", "Do something", ["Col A"])
        dialog.confirm_check.setChecked(True)
        dialog.confirm_check.setChecked(False)
        assert not dialog.apply_btn.isEnabled()

    def it_should_set_window_title(self):
        dialog = PreviewDialog("My Title", "Do something", ["Col A"])
        assert dialog.windowTitle() == "My Title"

    def it_should_configure_correct_column_headers(self):
        headers = ["Date", "Amount", "Description"]
        dialog = PreviewDialog("Title", "Do something", headers)
        assert dialog.table.columnCount() == 3
        assert dialog.table.horizontalHeaderItem(0).text() == "Date"
        assert dialog.table.horizontalHeaderItem(2).text() == "Description"
