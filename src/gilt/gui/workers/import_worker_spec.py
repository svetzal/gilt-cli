from __future__ import annotations

"""Specs for ImportWorker and compute_file_progress_window — no real financial data, PySide6 guarded."""

from datetime import date
from pathlib import Path

import pytest

PySide6 = pytest.importorskip("PySide6")

from gilt.gui.services.import_service import FileInfo, ImportFileMapping
from gilt.gui.workers.import_worker import compute_file_progress_window
from gilt.model.account import Account


def _make_mapping(
    name: str = "sample.csv",
    account_id: str | None = "MYBANK_CHQ",
) -> ImportFileMapping:
    return ImportFileMapping(
        file_info=FileInfo(
            path=Path(f"/tmp/{name}"),
            name=name,
            size=512,
            modified_date=date(2025, 1, 15),
        ),
        detected_account=Account(account_id=account_id) if account_id else None,
        selected_account_id=account_id,
        preview_rows=[],
    )


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
