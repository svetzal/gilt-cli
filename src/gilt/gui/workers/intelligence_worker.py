from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from PySide6.QtCore import QThread, Signal

from gilt.model.account import TransactionGroup
from gilt.model.errors import DATA_IO_ERRORS
from gilt.services.duplicate_service import DuplicateService
from gilt.services.intelligence_scan_service import IntelligenceScanService
from gilt.services.smart_category_service import SmartCategoryService

logger = logging.getLogger(__name__)


class IntelligenceWorker(QThread):
    """Worker thread for background intelligence scanning."""

    finished = Signal(dict)
    error = Signal(str)
    status = Signal(str)
    progress = Signal(int, int)

    def __init__(
        self,
        transactions: list[TransactionGroup],
        duplicate_service: DuplicateService,
        smart_category_service: SmartCategoryService,
        projections_path: Path | None = None,
    ):
        super().__init__()
        self.transactions = transactions
        self.duplicate_service = duplicate_service
        self.smart_category_service = smart_category_service
        self.projections_path = projections_path

    def run(self):
        try:
            scan_service = IntelligenceScanService()
            all_txns = [g.primary for g in self.transactions]

            uncategorized = [t for t in all_txns if not t.category]
            total_units = (
                (1 if self.duplicate_service else 0)
                + (1 if self.projections_path else 0)
                + (len(uncategorized) if self.smart_category_service else 0)
            )
            completed = 0
            metadata: dict = {}

            if self.duplicate_service:
                if self.isInterruptionRequested():
                    return
                self.status.emit("Scanning for duplicates...")
                metadata.update(scan_service.find_duplicates(all_txns, self.duplicate_service))
                completed += 1
                self.progress.emit(completed, total_units)

            rule_matched_ids: set[str] = set()
            if self.projections_path and self.projections_path.exists():
                if self.isInterruptionRequested():
                    return
                self.status.emit("Applying inferred rules...")
                try:
                    fragment = scan_service.run_inferred_rules(all_txns, self.projections_path)
                    metadata.update(fragment)
                    rule_matched_ids = set(fragment.keys())
                except DATA_IO_ERRORS + (sqlite3.OperationalError,) as e:
                    self.status.emit(f"Rule inference skipped: {e}")
                completed += 1
                self.progress.emit(completed, total_units)

            if self.smart_category_service:
                if self.isInterruptionRequested():
                    return
                self.status.emit("Predicting categories...")
                completed = self._predict_with_progress(
                    scan_service, all_txns, rule_matched_ids, metadata, completed, total_units
                )
                if completed is None:
                    return

            if not self.isInterruptionRequested():
                self.finished.emit(metadata)
        except DATA_IO_ERRORS as e:
            logger.error("Intelligence scan failed", exc_info=True)
            self.error.emit(f"Intelligence scan failed: {e}")

    def _predict_with_progress(
        self, scan_service, all_txns, rule_matched_ids, metadata, completed, total_units
    ) -> int | None:
        """Predict categories for uncategorized transactions, emitting progress. Returns None if interrupted."""
        for txn in all_txns:
            if self.isInterruptionRequested():
                return None
            if not txn.category and txn.transaction_id not in rule_matched_ids:
                fragment = scan_service.predict_categories([txn], self.smart_category_service)
                for tid, data in fragment.items():
                    if tid in metadata:
                        metadata[tid].update(data)
                    else:
                        metadata[tid] = data
                completed += 1
                self.progress.emit(completed, total_units)
        return completed
