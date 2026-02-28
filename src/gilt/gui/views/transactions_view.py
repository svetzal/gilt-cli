from __future__ import annotations

"""
Transactions View - Main view for browsing and filtering transactions

Provides filter controls and transaction table for comprehensive transaction management.
"""

import contextlib
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QStatusBar,
    QVBoxLayout,
    QWidget,
)

from gilt.gui.dialogs.categorize_dialog import CategorizeDialog
from gilt.gui.dialogs.duplicate_resolution_dialog import DuplicateResolutionDialog
from gilt.gui.dialogs.note_dialog import NoteDialog
from gilt.gui.dialogs.settings_dialog import SettingsDialog
from gilt.gui.dialogs.transaction_detail_dialog import TransactionDetailDialog
from gilt.gui.services.enrichment_service import EnrichmentService
from gilt.gui.services.transaction_service import TransactionService
from gilt.gui.widgets.transaction_table import TransactionTableWidget
from gilt.model.account import TransactionGroup
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv
from gilt.services.duplicate_service import DuplicateService
from gilt.services.smart_category_service import SmartCategoryService
from gilt.storage.event_store import EventStore


class IntelligenceWorker(QThread):
    """Worker thread for background intelligence scanning."""

    finished = Signal(dict)  # metadata dict

    def __init__(
        self,
        transactions: list[TransactionGroup],
        duplicate_service: DuplicateService,
        smart_category_service: SmartCategoryService,
    ):
        super().__init__()
        self.transactions = transactions
        self.duplicate_service = duplicate_service
        self.smart_category_service = smart_category_service

    def run(self):
        metadata = {}
        all_txns = [g.primary for g in self.transactions]

        if self.duplicate_service and not self._scan_duplicates(all_txns, metadata):
            return

        if self.smart_category_service and not self._predict_categories(all_txns, metadata):
            return

        if not self.isInterruptionRequested():
            self.finished.emit(metadata)

    def _scan_duplicates(self, all_txns, metadata: dict) -> bool:
        """Scan for duplicates and populate metadata. Returns False if interrupted."""
        if self.isInterruptionRequested():
            return False
        matches = self.duplicate_service.scan_transactions(all_txns)
        for m in matches:
            if self.isInterruptionRequested():
                return False
            for tid in [m.pair.txn1_id, m.pair.txn2_id]:
                if tid not in metadata:
                    metadata[tid] = {}
                metadata[tid]["risk"] = True
                metadata[tid]["duplicate_match"] = m
        return True

    def _predict_categories(self, all_txns, metadata: dict) -> bool:
        """Predict categories for uncategorized transactions. Returns False if interrupted."""
        for txn in all_txns:
            if self.isInterruptionRequested():
                return False
            if not txn.category:
                cat, conf = self.smart_category_service.predict_category(
                    txn.description, txn.amount, txn.account_id
                )
                if txn.transaction_id not in metadata:
                    metadata[txn.transaction_id] = {}
                metadata[txn.transaction_id]["confidence"] = conf
                metadata[txn.transaction_id]["predicted_category"] = cat
        return True


class TransactionsView(QWidget):
    """View for browsing and filtering transactions."""

    # Signal emitted when transactions are loaded
    transactions_loaded = Signal(int)  # count

    def __init__(
        self,
        data_dir: Path,
        duplicate_service: DuplicateService = None,
        smart_category_service: SmartCategoryService = None,
        event_store: EventStore = None,
        parent=None,
    ):
        super().__init__(parent)

        self.service = TransactionService(data_dir)
        self.duplicate_service = duplicate_service
        self.smart_category_service = smart_category_service
        self.event_store = event_store
        self.enrichment_service: EnrichmentService | None = None
        self._all_transactions: list[TransactionGroup] = []
        self.worker: IntelligenceWorker | None = None
        self._old_workers: list[IntelligenceWorker] = []

        # Initialize CategoryService
        from gilt.gui.dialogs.settings_dialog import SettingsDialog
        from gilt.gui.services.category_service import CategoryService

        categories_config = SettingsDialog.get_categories_config()
        self.category_service = CategoryService(categories_config)

        self._load_enrichment()
        self._init_ui()
        self._connect_signals()

        # Load initial data
        self.reload_transactions()

    def _load_enrichment(self):
        """Load enrichment data from event store."""
        if not self.event_store:
            return
        try:
            events = self.event_store.get_events_by_type("TransactionEnriched")
            self.enrichment_service = EnrichmentService(events)
        except Exception:
            self.enrichment_service = None

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Filter controls
        filter_group = self._create_filter_controls()
        layout.addWidget(filter_group)

        # Transaction table
        self.table = TransactionTableWidget(self)
        layout.addWidget(self.table)

        # Status bar at bottom
        self.status_bar = QStatusBar(self)
        layout.addWidget(self.status_bar)

        self._update_status()

        # Set categories for inline editing
        all_cats = []
        for c in self.category_service.get_all_categories():
            all_cats.append(c.name)
            for sub in c.subcategories:
                all_cats.append(f"{c.name}: {sub.name}")
        self.table.set_categories(all_cats)

        # Set enrichment service on model
        if self.enrichment_service:
            self.table.transaction_model.set_enrichment_service(self.enrichment_service)

        # Connect update signal
        self.table.transaction_model.transaction_updated.connect(self._on_transaction_updated)

    def _create_filter_controls(self) -> QGroupBox:
        """Create the filter controls group."""
        group = QGroupBox("Filters")
        layout = QVBoxLayout(group)

        # First row: Account, Date Range
        row1 = QHBoxLayout()

        # Account filter
        row1.addWidget(QLabel("Account:"))
        self.account_combo = QComboBox()
        self.account_combo.addItem("All Accounts", None)
        row1.addWidget(self.account_combo)

        row1.addSpacing(20)

        # Date range
        row1.addWidget(QLabel("From:"))
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        row1.addWidget(self.start_date_edit)

        row1.addWidget(QLabel("To:"))
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        row1.addWidget(self.end_date_edit)

        row1.addStretch()
        layout.addLayout(row1)

        # Second row: Search, Category, Uncategorized checkbox
        row2 = QHBoxLayout()

        # Search box
        row2.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search description...")
        row2.addWidget(self.search_edit)

        row2.addSpacing(20)

        # Category filter
        row2.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories", None)
        row2.addWidget(self.category_combo)

        row2.addSpacing(20)

        # Uncategorized checkbox
        self.uncategorized_check = QCheckBox("Show only uncategorized")
        row2.addWidget(self.uncategorized_check)

        row2.addStretch()
        layout.addLayout(row2)

        # Third row: Action buttons
        row3 = QHBoxLayout()

        self.apply_btn = QPushButton("Apply Filters")
        self.apply_btn.setDefault(True)
        row3.addWidget(self.apply_btn)

        self.clear_btn = QPushButton("Clear Filters")
        row3.addWidget(self.clear_btn)

        self.reload_btn = QPushButton("Reload from Disk")
        row3.addWidget(self.reload_btn)

        row3.addStretch()
        layout.addLayout(row3)

        return group

    def _connect_signals(self):
        """Connect signals to slots."""
        self.apply_btn.clicked.connect(self.apply_filters)
        self.clear_btn.clicked.connect(self.clear_filters)
        self.reload_btn.clicked.connect(self.reload_transactions)

        # Apply filters on Enter in search box
        self.search_edit.returnPressed.connect(self.apply_filters)

        # Update status when selection changes
        self.table.selection_changed.connect(self._update_status)

        # Context menu actions
        self.table.categorize_requested.connect(self._on_categorize_requested)
        self.table.note_requested.connect(self._on_note_requested)
        self.table.duplicate_resolution_requested.connect(self._on_resolve_duplicate_requested)
        self.table.manual_merge_requested.connect(self._on_manual_merge_requested)

        # Double-click for detail view
        self.table.detail_requested.connect(self._on_detail_requested)

    def reload_transactions(self):
        """Reload all transactions from disk."""
        # Refresh enrichment data
        self._load_enrichment()
        if self.enrichment_service:
            self.table.transaction_model.set_enrichment_service(self.enrichment_service)

        # Clear cache
        self.service.clear_cache()

        # Load all transactions
        self._all_transactions = self.service.load_all_transactions()

        # Update account combo
        self._update_account_combo()

        # Update category combo
        self._update_category_combo()

        # Apply current filters
        self.apply_filters()

        # Emit signal
        self.transactions_loaded.emit(len(self._all_transactions))

        # Start intelligence scan
        self._start_intelligence_scan()

    def _start_intelligence_scan(self):
        """Start background scan for duplicates and categorization."""
        if not self.duplicate_service and not self.smart_category_service:
            return

        # Handle existing worker
        if self.worker and self.worker.isRunning():
            self.worker.requestInterruption()
            # Disconnect signals to prevent stale updates
            with contextlib.suppress(RuntimeError):
                self.worker.finished.disconnect(self._on_intelligence_scan_finished)
            # Keep reference to prevent GC while running
            self._old_workers.append(self.worker)

        # Clean up finished old workers
        self._old_workers = [w for w in self._old_workers if w.isRunning()]

        self.worker = IntelligenceWorker(
            self._all_transactions, self.duplicate_service, self.smart_category_service
        )
        self.worker.finished.connect(self._on_intelligence_scan_finished)
        self.worker.start()

    def _on_intelligence_scan_finished(self, metadata: dict):
        """Handle completion of intelligence scan."""
        # Update model with new metadata
        self.table._model.update_metadata(metadata)
        self._update_status()

    def _update_account_combo(self):
        """Update the account combo box with available accounts."""
        current = self.account_combo.currentData()

        self.account_combo.clear()
        self.account_combo.addItem("All Accounts", None)

        accounts = self.service.get_available_accounts()
        for account_id in accounts:
            self.account_combo.addItem(account_id, account_id)

        # Restore previous selection if possible
        if current:
            index = self.account_combo.findData(current)
            if index >= 0:
                self.account_combo.setCurrentIndex(index)

    def _update_category_combo(self):
        """Update the category combo box with available categories."""
        current = self.category_combo.currentData()

        self.category_combo.clear()
        self.category_combo.addItem("All Categories", None)

        categories = self.service.get_unique_categories(self._all_transactions)
        for category in categories:
            self.category_combo.addItem(category, category)

        # Restore previous selection if possible
        if current:
            index = self.category_combo.findData(current)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)

    def apply_filters(self):
        """Apply current filter settings to the transaction list."""
        # Get filter values
        account_filter = None
        if self.account_combo.currentData():
            account_filter = [self.account_combo.currentData()]

        start_qdate = self.start_date_edit.date()
        start_date = date(start_qdate.year(), start_qdate.month(), start_qdate.day())

        end_qdate = self.end_date_edit.date()
        end_date = date(end_qdate.year(), end_qdate.month(), end_qdate.day())

        category_filter = None
        if self.category_combo.currentData():
            category_filter = [self.category_combo.currentData()]

        search_text = self.search_edit.text().strip() or None

        uncategorized_only = self.uncategorized_check.isChecked()

        # Apply filters using service
        filtered = self.service.filter_transactions(
            self._all_transactions,
            account_filter=account_filter,
            start_date=start_date,
            end_date=end_date,
            category_filter=category_filter,
            search_text=search_text,
            uncategorized_only=uncategorized_only,
        )

        # Update table
        self.table.update_transactions(filtered)

        # Update status
        self._update_status()

    def clear_filters(self):
        """Clear all filter settings."""
        self.account_combo.setCurrentIndex(0)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        self.end_date_edit.setDate(QDate.currentDate())
        self.category_combo.setCurrentIndex(0)
        self.search_edit.clear()
        self.uncategorized_check.setChecked(False)

        self.apply_filters()

    def _update_status(self):
        """Update status bar with current state."""
        displayed = self.table.get_row_count()
        total = len(self._all_transactions)

        selected = len(self.table.get_selected_transactions())

        if displayed == total:
            status_text = f"Showing {total} transactions"
        else:
            status_text = f"Showing {displayed} of {total} transactions"

        if selected > 0:
            status_text += f" | {selected} selected"

        self.status_bar.showMessage(status_text)

    def get_selected_transactions(self) -> list[TransactionGroup]:
        """Get currently selected transactions."""
        return self.table.get_selected_transactions()

    def _on_categorize_requested(self):
        """Handle categorize request from context menu."""
        selected = self.table.get_selected_transactions()
        if not selected:
            return

        # Get categories config path
        categories_config = SettingsDialog.get_categories_config()

        # Get suggestion if available
        suggestion = None
        if self.smart_category_service and len(selected) > 0:
            txn = selected[0].primary
            cat, _ = self.smart_category_service.predict_category(
                txn.description, txn.amount, txn.account_id
            )
            if cat:
                parts = cat.split(":", 1)
                suggestion = (parts[0], parts[1]) if len(parts) == 2 else (parts[0], None)

        # Show categorize dialog
        dialog = CategorizeDialog(selected, categories_config, self, suggested_category=suggestion)
        if dialog.exec():
            # Get selected category
            category, subcategory = dialog.get_selected_category()

            # Apply categorization
            self._apply_categorization(selected, category, subcategory)

    def _apply_categorization(
        self,
        transactions: list[TransactionGroup],
        category: str,
        subcategory: str | None,
    ):
        """
        Apply categorization to transactions and save to disk.

        Args:
            transactions: List of transactions to categorize
            category: Category name
            subcategory: Optional subcategory name
        """
        try:
            # Group transactions by account
            by_account = {}
            for txn_group in transactions:
                account_id = txn_group.primary.account_id
                if account_id not in by_account:
                    by_account[account_id] = []
                by_account[account_id].append(txn_group.primary.transaction_id)

            # Update each account file
            for account_id, txn_ids in by_account.items():
                ledger_path = self.service.data_dir / f"{account_id}.csv"
                if not ledger_path.exists():
                    continue

                # Load ledger
                text = ledger_path.read_text(encoding="utf-8")
                groups = load_ledger_csv(text)

                # Update transactions
                for group in groups:
                    if group.primary.transaction_id in txn_ids:
                        group.primary.category = category
                        group.primary.subcategory = subcategory

                # Save back to file
                updated_csv = dump_ledger_csv(groups)
                ledger_path.write_text(updated_csv, encoding="utf-8")

            # Reload transactions
            self.reload_transactions()

            # Show success message
            QMessageBox.information(
                self,
                "Success",
                f"Categorized {len(transactions)} transaction(s) as '{category}"
                + (f":{subcategory}'" if subcategory else "'"),
            )

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to categorize transactions:\n{str(e)}")

    def _on_note_requested(self):
        """Handle note edit request from context menu."""
        selected = self.table.get_selected_transactions()
        if len(selected) != 1:
            return

        txn_group = selected[0]
        txn = txn_group.primary

        # Show note dialog
        dialog = NoteDialog(
            current_note=txn.notes or "",
            transaction_desc=txn.description or "",
            parent=self,
        )

        if dialog.exec():
            # Get new note
            new_note = dialog.get_note()

            # Apply note
            self._apply_note(txn_group, new_note)

    def _apply_note(self, transaction: TransactionGroup, note: str):
        """
        Apply note to a transaction and save to disk.

        Args:
            transaction: Transaction to update
            note: New note text
        """
        try:
            account_id = transaction.primary.account_id
            ledger_path = self.service.data_dir / f"{account_id}.csv"

            if not ledger_path.exists():
                raise FileNotFoundError(f"Ledger file not found: {ledger_path}")

            # Load ledger
            text = ledger_path.read_text(encoding="utf-8")
            groups = load_ledger_csv(text)

            # Update transaction
            for group in groups:
                if group.primary.transaction_id == transaction.primary.transaction_id:
                    group.primary.notes = note if note else None
                    break

            # Save back to file
            updated_csv = dump_ledger_csv(groups)
            ledger_path.write_text(updated_csv, encoding="utf-8")

            # Reload transactions
            self.reload_transactions()

            # Show success message
            QMessageBox.information(self, "Success", "Note updated successfully")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to update note:\n{str(e)}")

    def _on_resolve_duplicate_requested(self):
        """Handle duplicate resolution request."""
        selected = self.table.get_selected_transactions()
        if len(selected) != 1:
            return

        txn = selected[0].primary
        meta = self.table._model.get_metadata(txn.transaction_id)
        match = meta.get("duplicate_match")

        if not match:
            QMessageBox.warning(self, "Error", "Duplicate match data not found.")
            return

        dialog = DuplicateResolutionDialog(match, self)
        if dialog.exec():
            is_duplicate, keep_id = dialog.get_resolution()

            try:
                # Record decision
                self.duplicate_service.resolve_duplicate(match, is_duplicate, keep_id)

                if is_duplicate:
                    # Determine which one to delete
                    delete_id = (
                        match.pair.txn2_id if keep_id == match.pair.txn1_id else match.pair.txn1_id
                    )
                    delete_account = (
                        match.pair.txn2_account
                        if keep_id == match.pair.txn1_id
                        else match.pair.txn1_account
                    )

                    # Delete from ledger
                    if self.service.delete_transaction(delete_id, delete_account):
                        QMessageBox.information(self, "Success", "Duplicate resolved and removed.")
                    else:
                        QMessageBox.warning(
                            self,
                            "Warning",
                            "Duplicate resolved but failed to remove transaction file.",
                        )
                else:
                    QMessageBox.information(self, "Success", "Marked as not a duplicate.")

                # Reload to refresh view and clear warnings
                self.reload_transactions()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to resolve duplicate:\n{str(e)}")

    def _on_manual_merge_requested(self):
        """Handle manual merge request for two selected transactions."""
        selected = self.table.get_selected_transactions()
        if len(selected) != 2:
            return

        txn1 = selected[0].primary
        txn2 = selected[1].primary

        # Create synthetic match
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

        # Reuse resolution dialog
        dialog = DuplicateResolutionDialog(match, self)
        if dialog.exec():
            is_duplicate, keep_id = dialog.get_resolution()

            if not is_duplicate:
                return

            try:
                # Record decision
                self.duplicate_service.resolve_duplicate(
                    match, is_duplicate, keep_id, rationale="Manual merge"
                )

                # Determine which one to delete
                delete_id = (
                    match.pair.txn2_id if keep_id == match.pair.txn1_id else match.pair.txn1_id
                )
                delete_account = (
                    match.pair.txn2_account
                    if keep_id == match.pair.txn1_id
                    else match.pair.txn1_account
                )

                # Delete from ledger
                if self.service.delete_transaction(delete_id, delete_account):
                    QMessageBox.information(self, "Success", "Transactions merged.")
                else:
                    QMessageBox.warning(
                        self, "Warning", "Merged but failed to remove duplicate transaction file."
                    )

                # Reload to refresh view
                self.reload_transactions()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to merge transactions:\n{str(e)}")

    def _on_detail_requested(self, transaction: TransactionGroup):
        """Handle double-click to show transaction detail dialog."""
        enrichment = None
        if self.enrichment_service:
            enrichment = self.enrichment_service.get_enrichment(transaction.primary.transaction_id)
        dialog = TransactionDetailDialog(transaction, enrichment, self)
        dialog.exec()

    def _on_transaction_updated(self, group: TransactionGroup):
        """Handle transaction update from table (inline edit)."""
        if self.service.update_transaction(group):
            pass
        else:
            QMessageBox.critical(self, "Error", "Failed to update transaction.")
            self.reload_transactions()
