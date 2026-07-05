from __future__ import annotations

from datetime import date
from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")

from gilt.gui.services.import_service import FileInfo, ImportFileMapping
from gilt.gui.views.import_wizard import (
    PAGE_ACCOUNT_MAPPING,
    PAGE_SELECT_FILES,
    ImportWizard,
    PreviewPage,
)
from gilt.model.account import Account


class _FakeImportService:
    def load_accounts(self):
        return [Account(account_id="MYBANK_CHQ"), Account(account_id="MYBANK_CC")]

    def build_file_mapping(self, file_path: Path, max_preview_rows: int = 5) -> ImportFileMapping:
        detected = Account(account_id="MYBANK_CHQ")
        file_info = FileInfo(
            path=file_path,
            name=file_path.name,
            size=1024,
            modified_date=date(2025, 1, 15),
        )
        return ImportFileMapping(
            file_info=file_info,
            detected_account=detected,
            selected_account_id="MYBANK_CHQ",
            preview_rows=[
                {"date": "2025-01-15", "amount": "-42.00", "description": "EXAMPLE UTILITY"},
                {"date": "2025-01-16", "amount": "-12.50", "description": "SAMPLE STORE"},
            ],
        )


def _make_file_info(name: str = "sample.csv") -> FileInfo:
    return FileInfo(
        path=Path(f"/tmp/{name}"),
        name=name,
        size=512,
        modified_date=date(2025, 1, 15),
    )


def _make_mapping(
    name: str = "sample.csv",
    account_id: str | None = "MYBANK_CHQ",
    preview_rows: list | None = None,
    error: str | None = None,
) -> ImportFileMapping:
    return ImportFileMapping(
        file_info=_make_file_info(name),
        detected_account=Account(account_id=account_id) if account_id else None,
        selected_account_id=account_id,
        preview_rows=preview_rows if preview_rows is not None else [],
        error=error,
    )


class DescribePreviewPageRendering:
    """PreviewPage._show_preview() exercised for all three rendering branches."""

    def it_should_show_error_cell_when_mapping_has_error(self, qapp):
        page = PreviewPage(_FakeImportService())
        mapping = _make_mapping(error="Failed to parse CSV")

        page._show_preview(mapping)

        assert page.table.rowCount() == 1
        assert page.table.columnCount() == 1
        cell_text = page.table.item(0, 0).text()
        assert "Error:" in cell_text
        assert "Failed to parse CSV" in cell_text

    def it_should_show_no_data_cell_when_preview_rows_empty(self, qapp):
        page = PreviewPage(_FakeImportService())
        mapping = _make_mapping(preview_rows=[])

        page._show_preview(mapping)

        assert page.table.rowCount() == 1
        assert page.table.item(0, 0).text() == "No preview data available"

    def it_should_derive_columns_from_first_row_keys(self, qapp):
        page = PreviewPage(_FakeImportService())
        mapping = _make_mapping(
            preview_rows=[
                {"date": "2025-01-15", "amount": "-42.00", "description": "EXAMPLE UTILITY"},
                {"date": "2025-01-16", "amount": "-12.50", "description": "SAMPLE STORE"},
            ]
        )

        page._show_preview(mapping)

        assert page.table.columnCount() == 3
        assert page.table.horizontalHeaderItem(0).text() == "date"
        assert page.table.horizontalHeaderItem(1).text() == "amount"
        assert page.table.horizontalHeaderItem(2).text() == "description"

    def it_should_populate_cell_values_from_preview_rows(self, qapp):
        page = PreviewPage(_FakeImportService())
        mapping = _make_mapping(
            preview_rows=[
                {"date": "2025-01-15", "amount": "-42.00", "description": "EXAMPLE UTILITY"},
                {"date": "2025-01-16", "amount": "-12.50", "description": "SAMPLE STORE"},
            ]
        )

        page._show_preview(mapping)

        assert page.table.rowCount() == 2
        assert page.table.item(0, 2).text() == "EXAMPLE UTILITY"
        assert page.table.item(1, 2).text() == "SAMPLE STORE"

    def it_should_set_summary_label_from_initializePage(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount,description\n")

        wizard = ImportWizard(_FakeImportService())
        wizard.page(PAGE_SELECT_FILES).selected_files = [csv_file]

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        mapping_page.initializePage()

        preview_page = wizard.page(2)  # PAGE_PREVIEW
        preview_page.initializePage()

        assert "sample.csv" in preview_page.summary_label.text()
