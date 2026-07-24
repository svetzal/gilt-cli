from __future__ import annotations

import logging

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from gilt.gui.dialogs.categorize_dialog import CategorizeDialog
from gilt.gui.dialogs.duplicate_resolution_dialog import DuplicateResolutionDialog
from gilt.gui.dialogs.note_dialog import NoteDialog
from gilt.gui.dialogs.settings_dialog import SettingsDialog
from gilt.model.account import TransactionGroup
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.model.errors import CONFIG_IO_ERRORS, DATA_IO_ERRORS
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_persistence_service import (
    CategorizationPersistenceService,
    CategorizationUpdate,
    persist_note_update,
)
from gilt.services.duplicate_service import DuplicateResolutionResult, DuplicateService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.event_store import EventStore

logger = logging.getLogger(__name__)


class TransactionMutationController(QObject):
    data_changed = Signal(object)  # restore_transaction_id (str | None)
    status_message = Signal(str)

    def __init__(
        self,
        event_store: EventStore | None,
        es_service: EventSourcingService | None,
        smart_category_service,
        service,
        duplicate_service: DuplicateService | None,
        parent_widget=None,
    ):
        super().__init__(parent_widget)
        self._event_store = event_store
        self._es_service = es_service
        self._smart_category_service = smart_category_service
        self._service = service
        self._duplicate_service = duplicate_service
        self._parent = parent_widget

    def _sync_projections(self):
        if not self._es_service or not self._event_store:
            return
        try:
            self._es_service.ensure_projections_up_to_date(self._event_store)
        except DATA_IO_ERRORS:
            self.status_message.emit("Warning: projections sync failed — view may be stale")

    def _run_prediction(self, transaction: TransactionGroup, predicted: str):
        """Apply a predicted category directly to a transaction."""
        parts = predicted.split(":", 1)
        category = parts[0].strip()
        subcategory = parts[1].strip() if len(parts) == 2 else None
        self._run_categorization(
            [transaction],
            category,
            subcategory,
            source="llm",
            restore_transaction_id=transaction.primary.transaction_id,
        )

    def categorize_selected(self, selected_transactions: list[TransactionGroup]):
        """Handle categorize request from context menu."""
        try:
            if not selected_transactions:
                return
            categories_config = SettingsDialog.get_categories_config()
            suggestion = None
            if self._smart_category_service and selected_transactions:
                txn = selected_transactions[0].primary
                cat, _ = self._smart_category_service.predict_category(
                    txn.description, txn.amount, txn.account_id
                )
                if cat:
                    parts = cat.split(":", 1)
                    suggestion = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], None)
            dialog = CategorizeDialog(
                selected_transactions,
                categories_config,
                self._parent,
                suggested_category=suggestion,
            )
            if dialog.exec():
                category, subcategory = dialog.get_selected_category()
                self._run_categorization(selected_transactions, category, subcategory)
        except CONFIG_IO_ERRORS as e:
            QMessageBox.critical(self._parent, "Error", f"Failed to open categorize dialog:\n{e}")

    def _run_categorization(
        self,
        transactions: list[TransactionGroup],
        category: str,
        subcategory: str | None,
        source: str = "user",
        restore_transaction_id: str | None = None,
    ):
        """Apply categorization to transactions and save to disk."""
        try:
            updates = [
                CategorizationUpdate(
                    transaction_id=txn_group.primary.transaction_id,
                    account_id=txn_group.primary.account_id,
                    category=category,
                    subcategory=subcategory,
                    source=source,
                    confidence=1.0,
                )
                for txn_group in transactions
            ]
            ledger_repo = LedgerRepository(self._service.data_dir)
            if self._event_store and self._es_service:
                persistence_svc = CategorizationPersistenceService(
                    event_store=self._event_store,
                    projection_builder=self._es_service.get_projection_builder(),
                    ledger_repo=ledger_repo,
                )
                persistence_svc.persist_categorizations(updates)
            else:
                from gilt.services.categorization_persistence_service import (
                    persist_categorizations_to_csv,
                )

                persist_categorizations_to_csv(updates, ledger_repo)
                self._sync_projections()
            if self._smart_category_service:
                for txn_group in transactions:
                    txn = txn_group.primary
                    self._smart_category_service.record_categorization(
                        transaction_id=txn.transaction_id,
                        category=category,
                        subcategory=subcategory,
                        source=source,
                        previous_category=txn.category,
                        previous_subcategory=txn.subcategory,
                    )
            self.data_changed.emit(restore_transaction_id)
        except DATA_IO_ERRORS as e:
            QMessageBox.critical(
                self._parent, "Error", f"Failed to categorize transactions:\n{str(e)}"
            )

    def note_selected(self, selected_transactions: list[TransactionGroup]):
        """Handle note edit request from context menu."""
        if len(selected_transactions) != 1:
            return
        txn_group = selected_transactions[0]
        txn = txn_group.primary
        dialog = NoteDialog(
            current_note=txn.notes or "",
            transaction_desc=txn.description or "",
            parent=self._parent,
        )
        if dialog.exec():
            new_note = dialog.get_note()
            self._run_note(txn_group, new_note)

    def _run_note(self, transaction: TransactionGroup, note: str):
        """Apply note to a transaction and save to disk."""
        try:
            persist_note_update(
                account_id=transaction.primary.account_id,
                transaction_id=transaction.primary.transaction_id,
                note=note if note else None,
                ledger_repo=LedgerRepository(self._service.data_dir),
            )
            self._sync_projections()
            self.data_changed.emit(None)
            QMessageBox.information(self._parent, "Success", "Note updated successfully")
        except DATA_IO_ERRORS as e:
            QMessageBox.critical(self._parent, "Error", f"Failed to update note:\n{str(e)}")

    def run_duplicate_resolution(self, txn_group: TransactionGroup, meta: dict):
        """Handle duplicate resolution request."""
        match = meta.get("duplicate_match")
        if not match:
            QMessageBox.warning(self._parent, "Error", "Duplicate match data not found.")
            return
        dialog = DuplicateResolutionDialog(match, self._parent)
        if dialog.exec():
            is_duplicate, keep_id = dialog.get_resolution()
            try:
                resolution: DuplicateResolutionResult = (
                    self._duplicate_service.run_duplicate_deletion(match, is_duplicate, keep_id)
                )
                if resolution.confirmed:
                    if self._service.delete_transaction(
                        resolution.delete_transaction_id, resolution.delete_account_id
                    ):
                        QMessageBox.information(
                            self._parent, "Success", "Duplicate resolved and removed."
                        )
                    else:
                        QMessageBox.warning(
                            self._parent,
                            "Warning",
                            "Duplicate resolved but failed to remove transaction file.",
                        )
                else:
                    QMessageBox.information(self._parent, "Success", "Marked as not a duplicate.")
                self._sync_projections()
                self.data_changed.emit(None)
            except DATA_IO_ERRORS as e:
                QMessageBox.critical(
                    self._parent, "Error", f"Failed to resolve duplicate:\n{str(e)}"
                )

    def manual_merge(self, selected_transactions: list[TransactionGroup]):
        """Handle manual merge request for two selected transactions."""
        if len(selected_transactions) != 2:
            return
        txn1 = selected_transactions[0].primary
        txn2 = selected_transactions[1].primary
        pair = TransactionPair(
            txn1_id=txn1.transaction_id,
            txn1_date=txn1.date,
            txn1_description=txn1.description,
            txn1_amount=txn1.amount,
            txn1_account=txn1.account_id,
            txn1_source_file=txn1.source_file,
            txn2_id=txn2.transaction_id,
            txn2_date=txn2.date,
            txn2_description=txn2.description,
            txn2_amount=txn2.amount,
            txn2_account=txn2.account_id,
            txn2_source_file=txn2.source_file,
        )
        assessment = DuplicateAssessment(
            is_duplicate=True, confidence=1.0, reasoning="Manually identified by user"
        )
        match = DuplicateMatch(pair=pair, assessment=assessment)
        dialog = DuplicateResolutionDialog(match, self._parent)
        if dialog.exec():
            is_duplicate, keep_id = dialog.get_resolution()
            if not is_duplicate:
                return
            try:
                resolution: DuplicateResolutionResult = (
                    self._duplicate_service.run_duplicate_deletion(
                        match, is_duplicate, keep_id, rationale="Manual merge"
                    )
                )
                if resolution.confirmed:
                    if self._service.delete_transaction(
                        resolution.delete_transaction_id, resolution.delete_account_id
                    ):
                        QMessageBox.information(self._parent, "Success", "Transactions merged.")
                    else:
                        QMessageBox.warning(
                            self._parent,
                            "Warning",
                            "Merged but failed to remove duplicate transaction file.",
                        )
                self._sync_projections()
                self.data_changed.emit(None)
            except DATA_IO_ERRORS as e:
                QMessageBox.critical(
                    self._parent, "Error", f"Failed to merge transactions:\n{str(e)}"
                )

    def on_transaction_updated(self, group: TransactionGroup):
        """Handle transaction update from table inline edit."""
        if self._service.update_transaction(group):
            txn = group.primary
            if self._smart_category_service and txn.category:
                self._smart_category_service.record_categorization(
                    transaction_id=txn.transaction_id,
                    category=txn.category,
                    subcategory=txn.subcategory,
                    source="user",
                )
            self._sync_projections()
        else:
            QMessageBox.critical(self._parent, "Error", "Failed to update transaction.")
            self.data_changed.emit(None)
