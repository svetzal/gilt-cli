from __future__ import annotations

from unittest.mock import MagicMock

import pytest

PySide6 = pytest.importorskip("PySide6")

from gilt.gui.views.import_wizard.pages.file_selection_page import FileSelectionPage


class _FakeImportService:
    pass


class DescribeFileSelectionPage:
    """FileSelectionPage real-widget behavior."""

    def it_should_be_incomplete_when_no_files_selected(self, qapp):
        page = FileSelectionPage(_FakeImportService())
        assert page.isComplete() is False

    def it_should_be_complete_when_files_are_present(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount\n")

        page = FileSelectionPage(_FakeImportService())
        page.selected_files.append(csv_file)

        assert page.isComplete() is True

    def it_should_remove_selected_file_from_list_and_selection(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount\n")

        page = FileSelectionPage(_FakeImportService())
        page.selected_files.append(csv_file)
        page.file_list.addItem(csv_file.name)
        page.file_list.setCurrentRow(0)

        page._on_remove_files()

        assert len(page.selected_files) == 0
        assert page.file_list.count() == 0

    def it_should_show_no_files_selected_in_info_label_for_zero_files(self, qapp):
        page = FileSelectionPage(_FakeImportService())

        page._update_info()

        assert "No files selected" in page.info_label.text()

    def it_should_show_singular_label_for_one_file(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount\n")

        page = FileSelectionPage(_FakeImportService())
        page.selected_files.append(csv_file)

        page._update_info()

        assert "1 file selected" in page.info_label.text()

    def it_should_show_plural_label_for_multiple_files(self, qapp, tmp_path):
        page = FileSelectionPage(_FakeImportService())
        for name in ("a.csv", "b.csv", "c.csv"):
            f = tmp_path / name
            f.write_text("date,amount\n")
            page.selected_files.append(f)

        page._update_info()

        assert "3 files selected" in page.info_label.text()

    def it_should_accept_only_csv_files_via_drop(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount\n")
        xls_file = tmp_path / "data.xlsx"
        xls_file.write_text("not csv")

        page = FileSelectionPage(_FakeImportService())

        event = MagicMock()
        csv_url = MagicMock()
        csv_url.toLocalFile.return_value = str(csv_file)
        xls_url = MagicMock()
        xls_url.toLocalFile.return_value = str(xls_file)
        event.mimeData.return_value.urls.return_value = [csv_url, xls_url]

        page._drop_event(event)

        assert csv_file in page.selected_files
        assert xls_file not in page.selected_files

    def it_should_not_add_duplicate_files_on_repeated_drop(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount\n")

        page = FileSelectionPage(_FakeImportService())

        event = MagicMock()
        url = MagicMock()
        url.toLocalFile.return_value = str(csv_file)
        event.mimeData.return_value.urls.return_value = [url]

        page._drop_event(event)
        page._drop_event(event)

        assert len(page.selected_files) == 1
