from __future__ import annotations

from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")

from datetime import date

from gilt.gui.services.import_service import FileInfo, ImportFileMapping
from gilt.gui.views.import_wizard import (
    PAGE_ACCOUNT_MAPPING,
    PAGE_SELECT_FILES,
    ImportWizard,
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
            ],
        )


class _NoDetectionImportService(_FakeImportService):
    def build_file_mapping(self, file_path: Path, max_preview_rows: int = 5) -> ImportFileMapping:
        file_info = FileInfo(
            path=file_path,
            name=file_path.name,
            size=512,
            modified_date=date(2025, 1, 15),
        )
        return ImportFileMapping(
            file_info=file_info,
            detected_account=None,
            selected_account_id=None,
            preview_rows=[],
        )


class DescribeAccountMappingPageInitialization:
    """AccountMappingPage.initializePage() exercised against a real widget."""

    def it_should_populate_table_rows_from_service_build_file_mapping(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount,description\n2025-01-15,-42.00,EXAMPLE UTILITY\n")

        wizard = ImportWizard(_FakeImportService())
        file_page = wizard.page(PAGE_SELECT_FILES)
        file_page.selected_files = [csv_file]

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        mapping_page.initializePage()

        assert mapping_page.table.rowCount() == 1
        assert mapping_page.table.item(0, 0).text() == "sample.csv"

    def it_should_show_detected_account_in_detected_column(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount,description\n")

        wizard = ImportWizard(_FakeImportService())
        wizard.page(PAGE_SELECT_FILES).selected_files = [csv_file]

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        mapping_page.initializePage()

        assert mapping_page.table.item(0, 1).text() == "MYBANK_CHQ"
        assert mapping_page.table.item(0, 3).text() == "✓ Ready"

    def it_should_show_unknown_when_no_account_detected(self, qapp, tmp_path):
        csv_file = tmp_path / "mystery.csv"
        csv_file.write_text("date,amount,description\n")

        wizard = ImportWizard(_NoDetectionImportService())
        wizard.page(PAGE_SELECT_FILES).selected_files = [csv_file]

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        mapping_page.initializePage()

        assert mapping_page.table.item(0, 1).text() == "Unknown"
        assert mapping_page.table.item(0, 3).text() == "⚠ Unknown"

    def it_should_report_incomplete_when_mapping_lacks_account(self, qapp, tmp_path):
        csv_file = tmp_path / "mystery.csv"
        csv_file.write_text("date,amount,description\n")

        wizard = ImportWizard(_NoDetectionImportService())
        wizard.page(PAGE_SELECT_FILES).selected_files = [csv_file]

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        mapping_page.initializePage()

        assert mapping_page.isComplete() is False

    def it_should_report_complete_when_all_mappings_have_account(self, qapp, tmp_path):
        csv_file = tmp_path / "sample.csv"
        csv_file.write_text("date,amount,description\n")

        wizard = ImportWizard(_FakeImportService())
        wizard.page(PAGE_SELECT_FILES).selected_files = [csv_file]

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        mapping_page.initializePage()

        assert mapping_page.isComplete() is True
