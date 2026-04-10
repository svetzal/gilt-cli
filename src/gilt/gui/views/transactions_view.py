from __future__ import annotations

"""
Transactions View - Main view for browsing and filtering transactions

Provides filter controls and transaction table for comprehensive transaction management.
"""

import contextlib
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt, QThread, Signal
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
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gilt.gui.dialogs.categorize_dialog import CategorizeDialog
from gilt.gui.dialogs.duplicate_resolution_dialog import DuplicateResolutionDialog
from gilt.gui.dialogs.note_dialog import NoteDialog
from gilt.gui.dialogs.receipt_match_dialog import (
    BatchReceiptMatchDialog,
    ReceiptMatchDialog,
)
from gilt.gui.dialogs.settings_dialog import SettingsDialog
from gilt.gui.services.enrichment_service import EnrichmentService
from gilt.gui.services.intelligence_cache import IntelligenceCache
from gilt.gui.services.receipt_match_service import ReceiptMatchService
from gilt.gui.services.transaction_service import TransactionService
from gilt.gui.widgets.transaction_detail_panel import TransactionDetailPanel
from gilt.gui.widgets.transaction_table import TransactionTableWidget
from gilt.model.account import TransactionGroup
from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.services.categorization_persistence_service import (
    CategorizationPersistenceService,
    CategorizationUpdate,
    persist_note_update,
)
from gilt.services.duplicate_service import DuplicateResolutionResult, DuplicateService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.services.intelligence_scan_service import IntelligenceScanService
from gilt.services.smart_category_service import SmartCategoryService
from gilt.storage.event_store import EventStore


class IntelligenceWorker(QThread):
    """Worker thread for background intelligence scanning."""

    finished = Signal(dict)  # metadata dict
    error = Signal(str)  # error message
    status = Signal(str)  # progress status
    progress = Signal(int, int)  # current, total

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
                metadata.update(scan_service.scan_duplicates(all_txns, self.duplicate_service))
                completed += 1
                self.progress.emit(completed, total_units)

            rule_matched_ids: set[str] = set()
            if self.projections_path and self.projections_path.exists():
                if self.isInterruptionRequested():
                    return
                self.status.emit("Applying inferred rules...")
                try:
                    fragment = scan_service.apply_inferred_rules(all_txns, self.projections_path)
                    metadata.update(fragment)
                    rule_matched_ids = set(fragment.keys())
                except Exception as e:
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
        except Exception as e:
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
                metadata.update(fragment)
                completed += 1
                self.progress.emit(completed, total_units)
        return completed


class TransactionsView(QWidget):
    """View for browsing and filtering transactions."""

    # Signal emitted when transactions are loaded
    transactions_loaded = Signal(int)  # count
    status_message = Signal(str)  # for main window status bar

    # Relay signals for background task progress
    scan_started = Signal(str, int)  # description, total
    scan_progress = Signal(int, int)  # current, total
    scan_finished = Signal()

    def __init__(
        self,
        data_dir: Path,
        duplicate_service: DuplicateService = None,
        smart_category_service: SmartCategoryService = None,
        event_store: EventStore = None,
        cache_path: Path | None = None,
        projections_path: Path | None = None,
        es_service: EventSourcingService | None = None,
        parent=None,
    ):
        super().__init__(parent)

        self.projections_path = (
            projections_path if projections_path is not None else data_dir.parent / "projections.db"
        )
        self.service = TransactionService(data_dir, projections_db_path=self.projections_path)
        self.duplicate_service = duplicate_service
        self.smart_category_service = smart_category_service
        self.event_store = event_store

        if es_service is not None:
            self.es_service: EventSourcingService | None = es_service
        elif event_store is not None:
            self.es_service = EventSourcingService(
                event_store_path=self.projections_path.parent / "events.db",
                projections_path=self.projections_path,
            )
        else:
            self.es_service = None
        self.enrichment_service: EnrichmentService | None = None
        self._all_transactions: list[TransactionGroup] = []
        self.worker: IntelligenceWorker | None = None
        self._old_workers: list[IntelligenceWorker] = []

        # Intelligence cache
        if cache_path is None:
            cache_path = data_dir.parent / "private" / "intelligence_cache.json"
        self._intelligence_cache = IntelligenceCache(cache_path)

        # Initialize CategoryService
        from gilt.gui.dialogs.settings_dialog import SettingsDialog
        from gilt.gui.services.category_service import CategoryService

        categories_config = SettingsDialog.get_categories_config()
        self.category_service = CategoryService(categories_config)

        self._load_enrichment()
        self._init_ui()
        self._connect_signals()

        # Stop background workers cleanly when the application exits
        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._stop_workers)

        # Load initial data
        self.reload_transactions()

    def _disconnect_all_worker_signals(self, worker: IntelligenceWorker) -> None:
        """Disconnect all signals from a worker to prevent callbacks on dead slots."""
        for sig in (worker.finished, worker.error, worker.status, worker.progress):
            with contextlib.suppress(RuntimeError):
                sig.disconnect()

    def _stop_workers(self) -> None:
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

    def _sync_projections(self):
        """Incrementally rebuild projections DB from new events."""
        if not self.es_service or not self.event_store:
            return
        try:
            self.es_service.ensure_projections_up_to_date(self.event_store)
        except (OSError, ValueError):
            self.status_message.emit("Warning: projections sync failed — view may be stale")

    def _load_enrichment(self):
        """Load enrichment data from event store."""
        if not self.event_store:
            return
        try:
            events = self.event_store.get_events_by_type("TransactionEnriched")
            self.enrichment_service = EnrichmentService(events)
        except (OSError, ValueError):
            self.enrichment_service = None

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Filter controls (fixed size, no vertical stretch)
        filter_group = self._create_filter_controls()
        layout.addWidget(filter_group, 0)

        # Splitter: table on left, detail panel on right (expands to fill)
        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Transaction table
        self.table = TransactionTableWidget(self)
        self._splitter.addWidget(self.table)

        # Detail panel (hidden by default)
        self.detail_panel = TransactionDetailPanel(self)
        self._splitter.addWidget(self.detail_panel)
        self.detail_panel.setVisible(False)

        # Give the table most of the space
        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)

        layout.addWidget(self._splitter, 1)

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

        # First row: Account, Date Range preset, custom dates
        row1 = QHBoxLayout()

        # Account filter
        row1.addWidget(QLabel("Account:"))
        self.account_combo = QComboBox()
        self.account_combo.addItem("All Accounts", None)
        row1.addWidget(self.account_combo)

        row1.addSpacing(20)

        # Date range preset
        row1.addWidget(QLabel("Period:"))
        self.date_range_combo = QComboBox()
        self.date_range_combo.addItems(
            [
                "This Month",
                "Last Month",
                "This Year",
                "Last Year",
                "All",
                "Custom",
            ]
        )
        row1.addWidget(self.date_range_combo)

        # Custom date range (hidden unless "Custom" selected)
        self._from_label = QLabel("From:")
        row1.addWidget(self._from_label)
        self.start_date_edit = QDateEdit()
        self.start_date_edit.setCalendarPopup(True)
        self.start_date_edit.setDate(QDate.currentDate().addMonths(-1))
        row1.addWidget(self.start_date_edit)

        self._to_label = QLabel("To:")
        row1.addWidget(self._to_label)
        self.end_date_edit = QDateEdit()
        self.end_date_edit.setCalendarPopup(True)
        self.end_date_edit.setDate(QDate.currentDate())
        row1.addWidget(self.end_date_edit)

        self._set_custom_dates_visible(False)

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

        # Status label
        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray;")
        row2.addWidget(self.status_label)

        layout.addLayout(row2)

        # Third row: utility buttons
        row3 = QHBoxLayout()

        self.clear_btn = QPushButton("Clear Filters")
        row3.addWidget(self.clear_btn)

        self.reload_btn = QPushButton("Reload from Disk")
        row3.addWidget(self.reload_btn)

        self.rescan_btn = QPushButton("Rescan Intelligence")
        row3.addWidget(self.rescan_btn)

        self.match_receipts_btn = QPushButton("Match Receipts")
        row3.addWidget(self.match_receipts_btn)

        row3.addStretch()
        layout.addLayout(row3)

        return group

    def _set_custom_dates_visible(self, visible: bool):
        """Show or hide the custom date range pickers."""
        self._from_label.setVisible(visible)
        self.start_date_edit.setVisible(visible)
        self._to_label.setVisible(visible)
        self.end_date_edit.setVisible(visible)

    def _on_date_range_changed(self, index: int):
        """Handle date range preset change."""
        preset = self.date_range_combo.currentText()
        today = QDate.currentDate()

        if preset == "Custom":
            self._set_custom_dates_visible(True)
            return

        self._set_custom_dates_visible(False)

        if preset == "This Month":
            start = QDate(today.year(), today.month(), 1)
            end = today
        elif preset == "Last Month":
            first_of_month = QDate(today.year(), today.month(), 1)
            end = first_of_month.addDays(-1)
            start = QDate(end.year(), end.month(), 1)
        elif preset == "This Year":
            start = QDate(today.year(), 1, 1)
            end = today
        elif preset == "Last Year":
            start = QDate(today.year() - 1, 1, 1)
            end = QDate(today.year() - 1, 12, 31)
        elif preset == "All":
            self.apply_filters()
            return
        else:
            return

        self.start_date_edit.setDate(start)
        self.end_date_edit.setDate(end)
        self.apply_filters()

    def _connect_signals(self):
        """Connect signals to slots."""
        self.clear_btn.clicked.connect(self.clear_filters)
        self.reload_btn.clicked.connect(self.reload_transactions)
        self.rescan_btn.clicked.connect(self._rescan_intelligence)

        # Auto-apply filters on any change
        self.account_combo.currentIndexChanged.connect(self.apply_filters)
        self.date_range_combo.currentIndexChanged.connect(self._on_date_range_changed)
        self.start_date_edit.dateChanged.connect(self.apply_filters)
        self.end_date_edit.dateChanged.connect(self.apply_filters)
        self.category_combo.currentIndexChanged.connect(self.apply_filters)
        self.uncategorized_check.stateChanged.connect(self.apply_filters)
        self.search_edit.textChanged.connect(self.apply_filters)

        # Update status and detail panel when selection changes
        self.table.selection_changed.connect(self._update_status)
        self.table.selection_changed.connect(self._on_selection_changed)

        # Context menu actions
        self.table.categorize_requested.connect(self._on_categorize_requested)
        self.table.apply_prediction_requested.connect(self._on_apply_prediction)
        self.table.note_requested.connect(self._on_note_requested)
        self.table.duplicate_resolution_requested.connect(self._on_resolve_duplicate_requested)
        self.table.manual_merge_requested.connect(self._on_manual_merge_requested)
        self.table.receipt_match_requested.connect(self._on_receipt_match_requested)
        self.detail_panel.receipt_match_requested.connect(self._on_receipt_match_requested)
        self.detail_panel.apply_prediction_requested.connect(self._on_apply_prediction)
        self.detail_panel.apply_receipt_requested.connect(self._on_apply_receipt_from_panel)
        self.match_receipts_btn.clicked.connect(self._on_batch_receipt_match)

    def reload_transactions(self, restore_transaction_id: str | None = None):
        """Reload all transactions from disk.

        Args:
            restore_transaction_id: If provided, re-select this transaction after reload.
        """
        # Refresh enrichment data
        self._load_enrichment()
        if self.enrichment_service:
            self.table.transaction_model.set_enrichment_service(self.enrichment_service)

        # Clear cache
        self.service.clear_cache()

        # Reset the view before swapping model data. QAbstractItemView.reset()
        # clears internal current-index, selection, scroll, and editor state so
        # no stale QModelIndex survives into the new data.
        self.table.reset()

        # Load all transactions into the stable source model
        self._all_transactions = self.service.load_all_transactions()
        self.table.set_all_transactions(self._all_transactions)

        # Update filter combos
        self._update_account_combo()
        self._update_category_combo()

        # Apply current filter criteria to proxy
        self.apply_filters()

        # Restore selection if requested
        if restore_transaction_id:
            self.table.select_transaction_by_id(restore_transaction_id)

        # Emit signal
        self.transactions_loaded.emit(len(self._all_transactions))

        # Start intelligence scan
        self._start_intelligence_scan()

    def _start_intelligence_scan(self):
        """Start background scan for duplicates and categorization."""
        if not self.duplicate_service and not self.smart_category_service:
            return

        # Load cached results immediately
        cached = self._intelligence_cache.get_all()
        if cached:
            self.table._model.update_metadata(cached)

        # Determine which transactions still need scanning
        all_ids = [g.primary.transaction_id for g in self._all_transactions]
        uncached_ids = self._intelligence_cache.uncached_transaction_ids(all_ids)

        if not uncached_ids:
            self.status_message.emit("Intelligence scan: all cached")
            return

        uncached_txns = [
            g for g in self._all_transactions if g.primary.transaction_id in uncached_ids
        ]

        # Handle existing worker — disconnect all signals regardless of running state
        if self.worker:
            if self.worker.isRunning():
                self.worker.requestInterruption()
                self._old_workers.append(self.worker)
            else:
                self.worker.wait(0)  # join finished OS thread
            self._disconnect_all_worker_signals(self.worker)
            self.worker = None

        # Clean up finished old workers — join stopped threads to release OS resources
        still_running = []
        for w in self._old_workers:
            if w.isRunning():
                still_running.append(w)
            else:
                w.wait(0)  # ensure OS thread is fully joined
        self._old_workers = still_running

        # Calculate total work units for progress
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
            projections_path=getattr(self, "projections_path", None),
        )
        self.worker.finished.connect(self._on_intelligence_scan_finished)
        self.worker.error.connect(self._on_intelligence_scan_error)
        self.worker.status.connect(self.status_message.emit)
        self.worker.progress.connect(self.scan_progress.emit)
        self.worker.start()

    def _on_intelligence_scan_finished(self, metadata: dict):
        """Handle completion of intelligence scan."""
        self._intelligence_cache.update(metadata)
        self.table._model.update_metadata(metadata)
        self._update_status()
        self.status_message.emit("Intelligence scan complete")
        self.scan_finished.emit()

    def _on_intelligence_scan_error(self, message: str):
        """Handle error from intelligence scan."""
        self.status_message.emit(message)
        self.scan_finished.emit()

    def _rescan_intelligence(self):
        """Clear the intelligence cache and rescan all transactions."""
        self._intelligence_cache.clear()
        self.table._model.clear_metadata()
        self._start_intelligence_scan()

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
        """Apply current filter criteria to the proxy model."""
        account_filter = None
        if self.account_combo.currentData():
            account_filter = [self.account_combo.currentData()]

        if self.date_range_combo.currentText() == "All":
            start_date = None
            end_date = None
        else:
            start_qdate = self.start_date_edit.date()
            start_date = date(start_qdate.year(), start_qdate.month(), start_qdate.day())

            end_qdate = self.end_date_edit.date()
            end_date = date(end_qdate.year(), end_qdate.month(), end_qdate.day())

        category_filter = None
        if self.category_combo.currentData():
            category_filter = [self.category_combo.currentData()]

        search_text = self.search_edit.text().strip() or None

        self.table.set_filters(
            account_filter=account_filter,
            start_date=start_date,
            end_date=end_date,
            category_filter=category_filter,
            search_text=search_text,
            uncategorized_only=self.uncategorized_check.isChecked(),
        )

        self._update_status()

    def clear_filters(self):
        """Clear all filter settings."""
        self.account_combo.setCurrentIndex(0)
        self.date_range_combo.setCurrentIndex(0)  # "This Month"
        self.category_combo.setCurrentIndex(0)
        self.search_edit.clear()
        self.uncategorized_check.setChecked(False)

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

        self.status_label.setText(status_text)

    def get_selected_transactions(self) -> list[TransactionGroup]:
        """Get currently selected transactions."""
        return self.table.get_selected_transactions()

    def _on_apply_prediction(self, transaction: TransactionGroup, predicted: str):
        """Apply a predicted category directly to a transaction."""
        parts = predicted.split(":", 1)
        category = parts[0].strip()
        subcategory = parts[1].strip() if len(parts) == 2 else None
        self._apply_categorization(
            [transaction],
            category,
            subcategory,
            source="llm",
            restore_transaction_id=transaction.primary.transaction_id,
        )

    def _on_categorize_requested(self):
        """Handle categorize request from context menu."""
        try:
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
            dialog = CategorizeDialog(
                selected, categories_config, self, suggested_category=suggestion
            )
            if dialog.exec():
                # Get selected category
                category, subcategory = dialog.get_selected_category()

                # Apply categorization
                self._apply_categorization(selected, category, subcategory)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to open categorize dialog:\n{e}")

    def _apply_categorization(
        self,
        transactions: list[TransactionGroup],
        category: str,
        subcategory: str | None,
        source: str = "user",
        restore_transaction_id: str | None = None,
    ):
        """
        Apply categorization to transactions and save to disk.

        Args:
            transactions: List of transactions to categorize
            category: Category name
            subcategory: Optional subcategory name
            source: Who assigned it ("user", "llm", "rule")
            restore_transaction_id: If set, re-select this transaction after reload.
        """
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

            if self.event_store and self.es_service:
                persistence_svc = CategorizationPersistenceService(
                    event_store=self.event_store,
                    projection_builder=self.es_service.get_projection_builder(),
                    ledger_data_dir=self.service.data_dir,
                )
                persistence_svc.persist_categorizations(updates)
            else:
                from gilt.services.categorization_persistence_service import (
                    write_categorizations_to_csv,
                )

                write_categorizations_to_csv(updates, self.service.data_dir)
                self._sync_projections()

            # Record categorization events for ML training
            if self.smart_category_service:
                for txn_group in transactions:
                    txn = txn_group.primary
                    self.smart_category_service.record_categorization(
                        transaction_id=txn.transaction_id,
                        category=category,
                        subcategory=subcategory,
                        source=source,
                        previous_category=txn.category,
                        previous_subcategory=txn.subcategory,
                    )

            # Reload transactions
            self.reload_transactions(restore_transaction_id=restore_transaction_id)

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
            persist_note_update(
                account_id=transaction.primary.account_id,
                transaction_id=transaction.primary.transaction_id,
                note=note if note else None,
                ledger_data_dir=self.service.data_dir,
            )

            # Sync projections DB so reload sees the updated data
            self._sync_projections()

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
                resolution: DuplicateResolutionResult = (
                    self.duplicate_service.resolve_and_identify_deletion(
                        match, is_duplicate, keep_id
                    )
                )

                if resolution.confirmed:
                    if self.service.delete_transaction(
                        resolution.delete_transaction_id, resolution.delete_account_id
                    ):
                        QMessageBox.information(self, "Success", "Duplicate resolved and removed.")
                    else:
                        QMessageBox.warning(
                            self,
                            "Warning",
                            "Duplicate resolved but failed to remove transaction file.",
                        )
                else:
                    QMessageBox.information(self, "Success", "Marked as not a duplicate.")

                # Sync projections DB so reload sees the updated data
                self._sync_projections()

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
                resolution: DuplicateResolutionResult = (
                    self.duplicate_service.resolve_and_identify_deletion(
                        match, is_duplicate, keep_id, rationale="Manual merge"
                    )
                )

                if resolution.confirmed:
                    if self.service.delete_transaction(
                        resolution.delete_transaction_id, resolution.delete_account_id
                    ):
                        QMessageBox.information(self, "Success", "Transactions merged.")
                    else:
                        QMessageBox.warning(
                            self,
                            "Warning",
                            "Merged but failed to remove duplicate transaction file.",
                        )

                # Sync projections DB so reload sees the updated data
                self._sync_projections()

                # Reload to refresh view
                self.reload_transactions()

            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to merge transactions:\n{str(e)}")

    def _get_receipt_match_service(self) -> ReceiptMatchService | None:
        """Create a ReceiptMatchService if event_store and receipts_dir are available."""
        if not self.event_store:
            return None
        receipts_dir = SettingsDialog.get_receipts_dir()
        if not receipts_dir.is_dir():
            QMessageBox.warning(
                self,
                "Receipts Directory",
                f"Receipts directory not found: {receipts_dir}\n\n"
                "Configure it in Settings > Paths.",
            )
            return None
        return ReceiptMatchService(receipts_dir, self.event_store)

    def _on_receipt_match_requested(self):
        """Handle receipt match request for a single selected transaction."""
        selected = self.table.get_selected_transactions()
        if len(selected) != 1:
            return

        svc = self._get_receipt_match_service()
        if not svc:
            return

        txn = selected[0].primary
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
            parent=self,
        )

        if dialog.exec():
            receipt = dialog.get_selected_receipt()
            if receipt:
                svc.apply_match(receipt, txn.transaction_id)
                self._load_enrichment()
                self.reload_transactions()
                QMessageBox.information(self, "Success", "Receipt matched successfully.")

    def _on_batch_receipt_match(self):
        """Handle batch receipt matching for unenriched transactions."""
        svc = self._get_receipt_match_service()
        if not svc:
            return

        # Filter to unenriched transactions
        unenriched = [
            g
            for g in self._all_transactions
            if not (
                self.enrichment_service
                and self.enrichment_service.is_enriched(g.primary.transaction_id)
            )
        ]

        if not unenriched:
            QMessageBox.information(
                self, "No Transactions", "All transactions already have receipt enrichment."
            )
            return

        self.status_message.emit(f"Matching receipts against {len(unenriched)} transactions...")

        result = svc.run_batch_matching(unenriched)

        if not result.matched and not result.ambiguous:
            QMessageBox.information(
                self,
                "No Matches",
                f"No receipt matches found.\nUnmatched receipts: {len(result.unmatched)}",
            )
            return

        dialog = BatchReceiptMatchDialog(
            matched=result.matched,
            ambiguous=result.ambiguous,
            unmatched=result.unmatched,
            parent=self,
        )

        if dialog.exec():
            resolved = dialog.get_resolved_matches()
            written = 0
            for match in resolved:
                confidence = match.match_confidence or "exact"
                svc.apply_match(match.receipt, match.transaction_id, confidence)
                written += 1

            if written:
                self._load_enrichment()
                self.reload_transactions()
                QMessageBox.information(
                    self, "Success", f"{written} receipt(s) matched successfully."
                )

        self.status_message.emit("Receipt matching complete.")

    def _on_selection_changed(self):
        """Update the detail panel when the table selection changes."""
        if not self.detail_panel.isVisible():
            return
        txn = self.table.get_current_transaction()
        enrichment = None
        metadata = None
        receipt_candidates = None
        if txn:
            if self.enrichment_service:
                enrichment = self.enrichment_service.get_enrichment(txn.primary.transaction_id)
            metadata = self.table._model.get_metadata(txn.primary.transaction_id)
            if not enrichment:
                receipt_candidates = self._find_receipt_candidates(txn)
        self.detail_panel.update_transaction(txn, enrichment, metadata, receipt_candidates)

    def _find_receipt_candidates(self, txn_group: TransactionGroup) -> list:
        """Find receipt candidates for a transaction."""
        svc = self._get_receipt_match_service()
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

    def _on_apply_receipt_from_panel(self, receipt, transaction_id: str):
        """Apply a receipt match selected from the detail panel."""
        svc = self._get_receipt_match_service()
        if not svc:
            return
        try:
            svc.apply_match(receipt, transaction_id)
            self.reload_transactions(restore_transaction_id=transaction_id)
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to apply receipt match:\n{str(e)}")

    def toggle_detail_panel(self):
        """Toggle the detail panel visibility."""
        visible = not self.detail_panel.isVisible()
        self.detail_panel.setVisible(visible)
        if visible:
            self._on_selection_changed()

    def _on_transaction_updated(self, group: TransactionGroup):
        """Handle transaction update from table (inline edit)."""
        if self.service.update_transaction(group):
            # Record categorization event for ML training
            txn = group.primary
            if self.smart_category_service and txn.category:
                self.smart_category_service.record_categorization(
                    transaction_id=txn.transaction_id,
                    category=txn.category,
                    subcategory=txn.subcategory,
                    source="user",
                )
            self._sync_projections()
        else:
            QMessageBox.critical(self, "Error", "Failed to update transaction.")
            self.reload_transactions()
