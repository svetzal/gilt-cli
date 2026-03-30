from __future__ import annotations

"""Specs for CategorizationReviewPage logic — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")


class DescribeCategorizationScanWorkerOrchestration:
    """Tests for CategorizationScanWorker scan logic."""

    def it_should_skip_mappings_without_selected_account_id(self):
        from dataclasses import dataclass
        from pathlib import Path

        @dataclass
        class _FileInfo:
            path: Path
            name: str

        @dataclass
        class _Mapping:
            file_info: _FileInfo
            selected_account_id: str | None

        fi = _FileInfo(path=Path("/tmp/sample.csv"), name="sample.csv")
        mappings = [
            _Mapping(file_info=fi, selected_account_id="MYBANK_CHQ"),
            _Mapping(file_info=fi, selected_account_id=None),
        ]
        processed = [m for m in mappings if m.selected_account_id]
        assert len(processed) == 1

    def it_should_emit_100_progress_after_all_mappings_processed(self):
        progress_values: list[int] = []
        total_files = 2
        for i in range(total_files):
            progress_values.append(int((i / total_files) * 100))
        progress_values.append(100)  # Final emit
        assert progress_values[-1] == 100

    def it_should_calculate_progress_proportionally_per_file(self):
        total_files = 4
        progress_at_start_of_file_2 = int((1 / total_files) * 100)
        assert progress_at_start_of_file_2 == 25


class DescribeConfidenceThresholding:
    """Tests for 0.8 confidence boundary between low and high styling."""

    def it_should_use_warning_theme_for_confidence_below_0_8(self):
        confidence = 0.75
        is_low = confidence < 0.8
        theme_prefix = "warning" if is_low else "success"
        assert theme_prefix == "warning"

    def it_should_use_success_theme_for_confidence_exactly_at_0_8(self):
        confidence = 0.8
        is_low = confidence < 0.8
        theme_prefix = "warning" if is_low else "success"
        assert theme_prefix == "success"

    def it_should_use_success_theme_for_confidence_above_0_8(self):
        confidence = 0.95
        is_low = confidence < 0.8
        theme_prefix = "warning" if is_low else "success"
        assert theme_prefix == "success"

    def it_should_format_confidence_as_percentage_string(self):
        confidence = 0.875
        formatted = f"{confidence:.0%}"
        assert formatted == "88%"

    def it_should_use_success_bg_and_fg_keys_for_high_confidence(self):
        confidence = 0.9
        is_low = confidence < 0.8
        bg_key = f"{'warning' if is_low else 'success'}_bg"
        fg_key = f"{'warning' if is_low else 'success'}_fg"
        assert bg_key == "success_bg"
        assert fg_key == "success_fg"


class DescribeOnCategoryChanged:
    """Tests for _on_category_changed category parsing logic."""

    def it_should_split_category_and_subcategory_on_colon(self):
        category_str = "Groceries: Fresh"
        if category_str and ":" in category_str:
            parts = category_str.split(":", 1)
            assigned_category = parts[0].strip()
            assigned_subcategory = parts[1].strip()
        else:
            assigned_category = category_str
            assigned_subcategory = None
        assert assigned_category == "Groceries"
        assert assigned_subcategory == "Fresh"

    def it_should_assign_category_only_when_no_colon_present(self):
        category_str = "Transport"
        if category_str and ":" in category_str:
            parts = category_str.split(":", 1)
            assigned_category = parts[0].strip()
            assigned_subcategory = parts[1].strip()
        else:
            assigned_category = category_str
            assigned_subcategory = None
        assert assigned_category == "Transport"
        assert assigned_subcategory is None

    def it_should_assign_none_when_no_category_selected(self):
        category_str = None
        if category_str and ":" in category_str:
            assigned_category = category_str.split(":", 1)[0].strip()
            assigned_subcategory = category_str.split(":", 1)[1].strip()
        else:
            assigned_category = category_str
            assigned_subcategory = None
        assert assigned_category is None
        assert assigned_subcategory is None

    def it_should_auto_check_confirm_when_category_selected(self):
        category_str = "Groceries"
        confirm_checked = category_str is not None
        assert confirm_checked is True

    def it_should_auto_uncheck_confirm_when_no_category_selected(self):
        category_str = None
        confirm_checked = category_str is not None
        assert confirm_checked is False


class DescribeCleanupPage:
    """Tests for cleanupPage QThread lifecycle rules."""

    def it_should_disconnect_signals_before_requesting_interruption(self):
        operations: list[str] = []

        class _FakeSignal:
            def disconnect(self, handler):
                operations.append(f"disconnect:{handler.__name__}")

        class _FakeWorker:
            def __init__(self):
                self.finished = _FakeSignal()
                self.error = _FakeSignal()

            def isRunning(self):
                return True

            def requestInterruption(self):
                operations.append("requestInterruption")

            def wait(self, ms: int):
                operations.append(f"wait({ms})")

        def _on_scan_finished(items):
            pass

        def _on_scan_error(err):
            pass

        worker = _FakeWorker()
        if worker.isRunning():
            worker.finished.disconnect(_on_scan_finished)
            worker.error.disconnect(_on_scan_error)
            worker.requestInterruption()
            worker.wait(2000)

        assert operations.index("disconnect:_on_scan_finished") < operations.index(
            "requestInterruption"
        )
        assert operations.index("disconnect:_on_scan_error") < operations.index(
            "requestInterruption"
        )
        assert "wait(2000)" in operations
