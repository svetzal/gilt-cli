from __future__ import annotations

import contextlib
import logging
from pathlib import Path

from PySide6.QtCore import QObject, Signal

from gilt.gui.services.intelligence_cache import IntelligenceCache
from gilt.gui.workers.intelligence_worker import IntelligenceWorker
from gilt.model.account import TransactionGroup
from gilt.services.duplicate_service import DuplicateService
from gilt.services.smart_category_service import SmartCategoryService

logger = logging.getLogger(__name__)


class IntelligenceScanController(QObject):
    status_message = Signal(str)
    scan_started = Signal(str, int)
    scan_progress = Signal(int, int)
    scan_finished = Signal()
    metadata_updated = Signal(dict)
    metadata_cleared = Signal()

    def __init__(
        self,
        intelligence_cache: IntelligenceCache,
        duplicate_service: DuplicateService | None,
        smart_category_service: SmartCategoryService | None,
        projections_path: Path | None,
        parent=None,
    ):
        super().__init__(parent)
        self._intelligence_cache = intelligence_cache
        self.duplicate_service = duplicate_service
        self.smart_category_service = smart_category_service
        self.projections_path = projections_path
        self.worker: IntelligenceWorker | None = None
        self._old_workers: list[IntelligenceWorker] = []

    def _disconnect_all_worker_signals(self, worker: IntelligenceWorker) -> None:
        """Disconnect all signals from a worker to prevent callbacks on dead slots."""
        for sig in (worker.finished, worker.error, worker.status, worker.progress):
            with contextlib.suppress(RuntimeError):
                sig.disconnect()

    def stop(self) -> None:
        """Interrupt and join all intelligence workers before the app exits."""
        if self.worker and self.worker.isRunning():
            self._disconnect_all_worker_signals(self.worker)
            self.worker.requestInterruption()
            self.worker.wait(3000)
        self.worker = None
        for w in self._old_workers:
            if w.isRunning():
                w.requestInterruption()
                w.wait(2000)
            else:
                w.wait(0)
        self._old_workers.clear()

    def rescan(self, all_transactions: list[TransactionGroup]) -> None:
        """Clear the intelligence cache and rescan all transactions."""
        self._intelligence_cache.clear()
        self.metadata_cleared.emit()
        self.start_scan(all_transactions)

    def start_scan(self, all_transactions: list[TransactionGroup]) -> None:
        """Start background scan for duplicates and categorization."""
        if not self.duplicate_service and not self.smart_category_service:
            return

        cached = self._intelligence_cache.get_all()
        if cached:
            self.metadata_updated.emit(cached)

        all_ids = [g.primary.transaction_id for g in all_transactions]
        uncached_ids = self._intelligence_cache.uncached_transaction_ids(all_ids)

        if not uncached_ids:
            self.status_message.emit("Intelligence scan: all cached")
            return

        uncached_txns = [g for g in all_transactions if g.primary.transaction_id in uncached_ids]

        if self.worker:
            if self.worker.isRunning():
                self.worker.requestInterruption()
                self._old_workers.append(self.worker)
            else:
                self.worker.wait(0)
            self._disconnect_all_worker_signals(self.worker)
            self.worker = None

        still_running = []
        for w in self._old_workers:
            if w.isRunning():
                still_running.append(w)
            else:
                w.wait(0)
        self._old_workers = still_running

        uncategorized_count = sum(1 for g in uncached_txns if not g.primary.category)
        total_units = 0
        if self.duplicate_service:
            total_units += 1
        if self.smart_category_service:
            total_units += uncategorized_count

        self.status_message.emit(f"Scanning {len(uncached_txns)} of {len(all_ids)} transactions...")
        self.scan_started.emit("Scanning...", total_units)

        self.worker = IntelligenceWorker(
            uncached_txns,
            self.duplicate_service,
            self.smart_category_service,
            projections_path=self.projections_path,
        )
        self.worker.finished.connect(self._on_scan_finished)
        self.worker.error.connect(self._on_scan_error)
        self.worker.status.connect(self.status_message.emit)
        self.worker.progress.connect(self.scan_progress.emit)
        self.worker.start()

    def _on_scan_finished(self, metadata: dict):
        """Handle completion of intelligence scan."""
        self._intelligence_cache.update(metadata)
        self.metadata_updated.emit(metadata)
        self.status_message.emit("Intelligence scan complete")
        self.scan_finished.emit()

    def _on_scan_error(self, message: str):
        """Handle error from intelligence scan."""
        self.status_message.emit(message)
        self.scan_finished.emit()
