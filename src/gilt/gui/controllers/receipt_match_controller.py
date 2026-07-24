from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from gilt.gui.dialogs.receipt_match_dialog import BatchReceiptMatchDialog, ReceiptMatchDialog
from gilt.gui.dialogs.settings_dialog import SettingsDialog
from gilt.gui.services.enrichment_service import EnrichmentService
from gilt.gui.services.receipt_match_service import ReceiptMatchService
from gilt.model.account import TransactionGroup
from gilt.model.errors import DATA_IO_ERRORS
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.event_store import EventStore

logger = logging.getLogger(__name__)


class ReceiptMatchController(QObject):
    data_changed = Signal(object)  # restore_transaction_id (str | None)
    status_message = Signal(str)

    def __init__(
        self,
        event_store: EventStore | None,
        es_service: EventSourcingService | None = None,
        parent_widget=None,
    ):
        super().__init__(parent_widget)
        self._event_store = event_store
        self._es_service = es_service
        self._parent = parent_widget

    def _sync_projections(self):
        if not self._es_service or not self._event_store:
            return
        try:
            self._es_service.ensure_projections_up_to_date(self._event_store)
        except DATA_IO_ERRORS:
            self.status_message.emit("Warning: projections sync failed — view may be stale")

    def get_service(self) -> ReceiptMatchService | None:
        """Create a ReceiptMatchService if event_store and receipts_dir are available."""
        if not self._event_store:
            return None
        receipts_dir = SettingsDialog.get_receipts_dir()
        if not receipts_dir.is_dir():
            QMessageBox.warning(
                self._parent,
                "Receipts Directory",
                f"Receipts directory not found: {receipts_dir}\n\n"
                "Configure it in Settings > Paths.",
            )
            return None
        return ReceiptMatchService(receipts_dir, self._event_store)

    def find_candidates(self, txn_group: TransactionGroup) -> list:
        """Find receipt candidates for a transaction."""
        svc = self.get_service()
        if not svc:
            return []
        txn = txn_group.primary
        return svc.find_candidates_for_transaction(
            txn_id=txn.transaction_id,
            txn_amount=txn.amount,
            txn_date=txn.date,
            txn_description=txn.description or "",
            txn_account_id=txn.account_id,
            txn_currency=txn.currency or "CAD",
        )

    def run_single_match(self, selected_transactions: list[TransactionGroup]) -> None:
        """Handle receipt match request for a single selected transaction."""
        if len(selected_transactions) != 1:
            return
        svc = self.get_service()
        if not svc:
            return
        txn = selected_transactions[0].primary
        candidates = svc.find_candidates_for_transaction(
            txn_id=txn.transaction_id,
            txn_amount=txn.amount,
            txn_date=txn.date,
            txn_description=txn.description or "",
            txn_account_id=txn.account_id,
            txn_currency=txn.currency or "CAD",
        )
        dialog = ReceiptMatchDialog(
            transaction_id=txn.transaction_id,
            transaction_desc=txn.description or "",
            transaction_amount=txn.amount,
            transaction_date=str(txn.date),
            candidates=candidates,
            parent=self._parent,
        )
        if dialog.exec():
            receipt = dialog.get_selected_receipt()
            if receipt:
                svc.run_match(receipt, txn.transaction_id)
                self._sync_projections()
                self.data_changed.emit(None)
                QMessageBox.information(self._parent, "Success", "Receipt matched successfully.")

    def run_batch_match(
        self,
        all_transactions: list[TransactionGroup],
        enrichment_service: EnrichmentService | None,
    ) -> None:
        """Handle batch receipt matching for unenriched transactions."""
        svc = self.get_service()
        if not svc:
            return
        unenriched = [
            g
            for g in all_transactions
            if not (enrichment_service and enrichment_service.is_enriched(g.primary.transaction_id))
        ]
        if not unenriched:
            QMessageBox.information(
                self._parent, "No Transactions", "All transactions already have receipt enrichment."
            )
            return
        self.status_message.emit(f"Matching receipts against {len(unenriched)} transactions...")
        result = svc.run_batch_matching(unenriched)
        if not result.matched and not result.ambiguous:
            QMessageBox.information(
                self._parent,
                "No Matches",
                f"No receipt matches found.\nUnmatched receipts: {len(result.unmatched)}",
            )
            return
        dialog = BatchReceiptMatchDialog(
            matched=result.matched,
            ambiguous=result.ambiguous,
            unmatched=result.unmatched,
            parent=self._parent,
        )
        if dialog.exec():
            resolved = dialog.get_resolved_matches()
            written = 0
            for match in resolved:
                confidence = match.match_confidence or "exact"
                svc.run_match(match.receipt, match.transaction_id, confidence)
                written += 1
            if written:
                self._sync_projections()
                self.data_changed.emit(None)
                QMessageBox.information(
                    self._parent, "Success", f"{written} receipt(s) matched successfully."
                )
        self.status_message.emit("Receipt matching complete.")

    def run_match_from_panel(self, receipt, transaction_id: str) -> None:
        """Apply a receipt match selected from the detail panel."""
        svc = self.get_service()
        if not svc:
            return
        try:
            svc.run_match(receipt, transaction_id)
            self._sync_projections()
            self.data_changed.emit(transaction_id)
        except DATA_IO_ERRORS as e:
            QMessageBox.critical(self._parent, "Error", f"Failed to apply receipt match:\n{str(e)}")
