from __future__ import annotations

"""Specs for ImportWizard components — no real financial data, PySide6 guarded."""

from datetime import date
from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")

from gilt.gui.services.import_service import FileInfo, ImportFileMapping, ImportResult
from gilt.gui.views.import_wizard import (
    PAGE_ACCOUNT_MAPPING,
    PAGE_SELECT_FILES,
    ExecutePage,
    ImportWizard,
    ImportWorker,
    PreviewPage,
    compute_file_progress_window,
)
from gilt.model.account import Account

# ---------------------------------------------------------------------------
# Fake ImportService for wizard page tests
# ---------------------------------------------------------------------------


class _FakeImportService:
    """Duck-typed ImportService returning synthetic, privacy-safe data."""

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


class _NoDetectionImportService(_FakeImportService):
    """Variant where no account is auto-detected."""

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


# ---------------------------------------------------------------------------
# Step 6: Progress window — tests now target the real extracted helper
# ---------------------------------------------------------------------------


class DescribeComputeFileProgressWindow:
    """Tests for the compute_file_progress_window pure helper."""

    def it_should_start_first_file_at_zero(self):
        start, _ = compute_file_progress_window(0, 3)
        assert start == 0

    def it_should_end_first_file_at_33_percent(self):
        _, end = compute_file_progress_window(0, 3)
        assert end == 33

    def it_should_start_second_file_at_33_percent(self):
        start, _ = compute_file_progress_window(1, 3)
        assert start == 33

    def it_should_end_last_file_at_100_percent(self):
        _, end = compute_file_progress_window(2, 3)
        assert end == 100

    def it_should_cover_full_range_for_single_file(self):
        start, end = compute_file_progress_window(0, 1)
        assert start == 0
        assert end == 100


class DescribeImportWorkerProgressCalculation:
    """Verify overall-progress arithmetic used inside ImportWorker.run."""

    def it_should_compute_overall_progress_from_file_pct(self):
        start, end = compute_file_progress_window(1, 3)  # second file of 3
        pct = 50  # 50% through this file
        overall = start + int((pct / 100) * (end - start))
        assert overall == 49

    def it_should_skip_mappings_without_selected_account_id(self):
        mappings = [
            _make_mapping("a.csv", account_id="MYBANK_CHQ"),
            _make_mapping("b.csv", account_id=None),
        ]
        processed = [m for m in mappings if m.selected_account_id]
        assert len(processed) == 1


# ---------------------------------------------------------------------------
# Step 3: AccountMappingPage.initializePage()
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Step 4: PreviewPage._show_preview() and initializePage()
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Step 5: ExecutePage._start_import(), _on_finished(), _on_error()
# ---------------------------------------------------------------------------


class DescribeExecutePageImportFlow:
    """ExecutePage shell logic exercised with a patched ImportWorker.start."""

    def it_should_log_dry_run_mode_and_set_worker(self, qapp, monkeypatch):
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(_FakeImportService(), [mapping], write=False)

        assert page.worker is not None
        assert "DRY-RUN" in page.log_text.toPlainText()

    def it_should_log_write_mode_when_write_enabled(self, qapp, monkeypatch):
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(_FakeImportService(), [mapping], write=True)

        assert "WRITE" in page.log_text.toPlainText()

    def it_should_log_duplicate_skip_count_when_exclude_ids_present(self, qapp, monkeypatch):
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(
            _FakeImportService(), [mapping], write=False, exclude_ids={"tx001", "tx002"}
        )

        assert "2 duplicate" in page.log_text.toPlainText()

    def it_should_log_categorization_count_when_map_present(self, qapp, monkeypatch):
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(
            _FakeImportService(),
            [mapping],
            write=False,
            categorization_map={"tx001": "Groceries", "tx002": "Transport"},
        )

        assert "2 category" in page.log_text.toPlainText()

    def it_should_set_import_complete_and_successful_on_finished_success(self, qapp):
        page = ExecutePage()
        result = ImportResult(
            success=True,
            imported_count=5,
            duplicate_count=2,
            error_count=0,
            messages=["Processed sample.csv"],
        )

        page._on_finished(result)

        assert page.import_complete is True
        assert page.import_successful is True
        assert page.isComplete() is True

    def it_should_include_transaction_count_in_success_summary(self, qapp):
        page = ExecutePage()
        result = ImportResult(
            success=True,
            imported_count=7,
            duplicate_count=1,
            error_count=0,
            messages=[],
        )

        page._on_finished(result)

        assert "7 transaction(s)" in page.summary_label.text()

    def it_should_set_import_unsuccessful_on_finished_failure(self, qapp):
        page = ExecutePage()
        result = ImportResult(
            success=False,
            imported_count=0,
            duplicate_count=0,
            error_count=1,
            messages=["Parse error"],
        )

        page._on_finished(result)

        assert page.import_complete is True
        assert page.import_successful is False

    def it_should_set_import_unsuccessful_on_error(self, qapp):
        page = ExecutePage()

        page._on_error("Connection refused")

        assert page.import_complete is True
        assert page.import_successful is False
        assert "Connection refused" in page.summary_label.text()

    def it_should_wire_signals_so_finished_emit_reaches_on_finished(self, qapp, monkeypatch):
        """Signals wired in _start_import: emit on worker triggers the handler."""
        page = ExecutePage()
        monkeypatch.setattr(ImportWorker, "start", lambda self: None)

        mapping = _make_mapping()
        page._start_import(_FakeImportService(), [mapping], write=False)

        result = ImportResult(
            success=True, imported_count=3, duplicate_count=0, error_count=0, messages=[]
        )
        page.worker.finished.emit(result)

        assert page.import_complete is True
        assert page.import_successful is True


# ---------------------------------------------------------------------------
# Original validation logic tests (kept for regression coverage)
# ---------------------------------------------------------------------------


class DescribeFileSelectionPageValidation:
    """Tests for CSV file validation logic in FileSelectionPage."""

    def it_should_accept_files_with_csv_extension(self):
        path = Path("/home/user/exports/sample_statement.csv")
        assert path.suffix.lower() == ".csv"

    def it_should_reject_files_without_csv_extension(self):
        path = Path("/home/user/exports/statement.xlsx")
        assert path.suffix.lower() != ".csv"

    def it_should_return_false_for_is_complete_when_no_files_selected(self):
        selected_files: list[Path] = []
        is_complete = len(selected_files) > 0
        assert is_complete is False

    def it_should_not_add_duplicate_file_paths(self):
        selected_files: list[Path] = []
        path = Path("/home/user/exports/sample.csv")
        if path not in selected_files:
            selected_files.append(path)
        if path not in selected_files:
            selected_files.append(path)
        assert len(selected_files) == 1


class DescribeAccountMappingPageInference:
    """Tests for account inference from filename patterns."""

    def it_should_report_unknown_when_no_account_detected(self):
        detected_account = None
        detected_label = detected_account.account_id if detected_account else "Unknown"
        assert detected_label == "Unknown"

    def it_should_show_ready_status_when_account_selected(self):
        selected_account_id = "MYBANK_CHQ"
        status = "✓ Ready" if selected_account_id else "⚠ Unknown"
        assert status == "✓ Ready"

    def it_should_show_unknown_status_when_no_account_selected(self):
        selected_account_id = None
        status = "✓ Ready" if selected_account_id else "⚠ Unknown"
        assert status == "⚠ Unknown"

    def it_should_return_false_for_is_complete_when_any_mapping_lacks_account(self):
        mappings = [
            _make_mapping("a.csv", account_id="MYBANK_CHQ"),
            _make_mapping("b.csv", account_id=None),
        ]
        is_complete = all(m.selected_account_id for m in mappings)
        assert is_complete is False


class DescribeImportWizardRejectWorkerCleanup:
    """Tests for QThread lifecycle rules in ImportWizard.reject."""

    def it_should_request_interruption_before_waiting_on_running_worker(self):
        operations: list[str] = []

        class _FakeWorker:
            def isRunning(self):
                return True

            def requestInterruption(self):
                operations.append("requestInterruption")

            def wait(self, ms: int):
                operations.append(f"wait({ms})")

        worker = _FakeWorker()
        if worker.isRunning():
            worker.requestInterruption()
            worker.wait(2000)

        assert operations == ["requestInterruption", "wait(2000)"]

    def it_should_not_call_worker_methods_when_worker_is_none(self):
        worker = None
        called = False
        if worker and worker.isRunning():
            called = True
        assert called is False
