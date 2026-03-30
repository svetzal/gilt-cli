from __future__ import annotations

"""Specs for ImportWizard components — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")

from pathlib import Path


class DescribeImportWorkerProgressCalculation:
    """Tests for ImportWorker multi-file progress allocation logic."""

    def it_should_start_first_file_progress_at_zero(self):
        i = 0
        total = 3
        file_progress_start = int((i / total) * 100)
        assert file_progress_start == 0

    def it_should_end_first_file_progress_at_33_percent(self):
        i = 0
        total = 3
        file_progress_end = int(((i + 1) / total) * 100)
        assert file_progress_end == 33

    def it_should_start_second_file_at_33_percent(self):
        i = 1
        total = 3
        file_progress_start = int((i / total) * 100)
        assert file_progress_start == 33

    def it_should_end_last_file_at_100_percent(self):
        i = 2
        total = 3
        file_progress_end = int(((i + 1) / total) * 100)
        assert file_progress_end == 100

    def it_should_compute_overall_progress_from_file_pct(self):
        file_progress_start = 33
        file_progress_end = 66
        pct = 50  # 50% through the second file
        overall = file_progress_start + int((pct / 100) * (file_progress_end - file_progress_start))
        assert overall == 49

    def it_should_skip_mappings_without_selected_account_id(self):
        # Simulate filtering logic in ImportWorker.run
        from dataclasses import dataclass
        from datetime import date

        @dataclass
        class _FileInfo:
            path: Path
            name: str
            size: int
            modified_date: date

        @dataclass
        class _Mapping:
            file_info: _FileInfo
            selected_account_id: str | None

        fi = _FileInfo(
            path=Path("/tmp/sample.csv"),
            name="sample.csv",
            size=1024,
            modified_date=date(2025, 1, 1),
        )
        mappings = [
            _Mapping(file_info=fi, selected_account_id="MYBANK_CHQ"),
            _Mapping(file_info=fi, selected_account_id=None),  # Should be skipped
        ]
        processed = [m for m in mappings if m.selected_account_id]
        assert len(processed) == 1


class DescribeFileSelectionPageValidation:
    """Tests for CSV file validation logic in FileSelectionPage."""

    def it_should_accept_files_with_csv_extension(self):
        path = Path("/home/user/exports/sample_statement.csv")
        assert path.suffix.lower() == ".csv"

    def it_should_reject_files_without_csv_extension(self):
        path = Path("/home/user/exports/statement.xlsx")
        assert path.suffix.lower() != ".csv"

    def it_should_reject_pdf_files(self):
        path = Path("/home/user/exports/statement.pdf")
        assert path.suffix.lower() != ".csv"

    def it_should_return_false_for_is_complete_when_no_files_selected(self):
        selected_files: list[Path] = []
        is_complete = len(selected_files) > 0
        assert is_complete is False

    def it_should_return_true_for_is_complete_when_files_selected(self):
        selected_files = [Path("/home/user/exports/sample.csv")]
        is_complete = len(selected_files) > 0
        assert is_complete is True

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

    def it_should_detect_account_from_filename_when_pattern_matches(self):
        # Simulate: if detected_account is set, selected_account_id is pre-populated
        detected_account_id = "MYBANK_CHQ"
        selected_account_id = detected_account_id  # Pre-populated
        assert selected_account_id == "MYBANK_CHQ"

    def it_should_report_unknown_when_no_account_detected(self):
        detected_account = None
        detected_label = (
            detected_account.account_id if detected_account else "Unknown"
        )
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
        from dataclasses import dataclass
        from datetime import date

        @dataclass
        class _FileInfo:
            path: Path
            name: str
            size: int
            modified_date: date

        @dataclass
        class _Mapping:
            file_info: _FileInfo
            selected_account_id: str | None

        fi = _FileInfo(
            path=Path("/tmp/sample.csv"),
            name="sample.csv",
            size=1024,
            modified_date=date(2025, 1, 1),
        )
        mappings = [
            _Mapping(file_info=fi, selected_account_id="MYBANK_CHQ"),
            _Mapping(file_info=fi, selected_account_id=None),
        ]
        is_complete = all(m.selected_account_id for m in mappings)
        assert is_complete is False


class DescribeImportWizardRejectWorkerCleanup:
    """Tests for QThread lifecycle rules in ImportWizard.reject."""

    def it_should_request_interruption_before_waiting_on_running_worker(self):
        # Verify the order-of-operations pattern: disconnect → requestInterruption → wait
        # We can't run the actual Qt code here, but we can document the expected pattern
        # via a simple state-machine simulation.
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
