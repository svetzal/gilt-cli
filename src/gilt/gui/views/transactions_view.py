from __future__ import annotations

"""
Transactions View - Main view for browsing and filtering transactions

Provides filter controls and transaction table for comprehensive transaction management.
"""

import logging
from datetime import date
from pathlib import Path

from PySide6.QtCore import QDate, Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDateEdit,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from gilt.gui.controllers.intelligence_scan_controller import IntelligenceScanController
from gilt.gui.controllers.receipt_match_controller import ReceiptMatchController
from gilt.gui.controllers.transaction_mutation_controller import TransactionMutationController
from gilt.gui.services.enrichment_service import EnrichmentService
from gilt.gui.services.intelligence_cache import IntelligenceCache
from gilt.gui.services.transaction_service import TransactionService, get_date_range
from gilt.gui.widgets.transaction_detail_panel import TransactionDetailPanel
from gilt.gui.widgets.transaction_table import TransactionTableWidget
from gilt.model.account import TransactionGroup
from gilt.model.errors import DATA_IO_ERRORS
from gilt.services.duplicate_service import DuplicateService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.services.smart_category_service import SmartCategoryService
from gilt.storage.event_store import EventStore

logger = logging.getLogger(__name__)


class TransactionsView(QWidget):
    """View for browsing and filtering transactions."""

    transactions_loaded = Signal(int)
    status_message = Signal(str)

    scan_started = Signal(str, int)
    scan_progress = Signal(int, int)
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

        if cache_path is None:
            cache_path = data_dir.parent / "private" / "intelligence_cache.json"
        self._intelligence_cache = IntelligenceCache(cache_path)

        from gilt.gui.dialogs.settings_dialog import SettingsDialog
        from gilt.gui.services.category_service import CategoryService

        categories_config = SettingsDialog.get_categories_config()
        self.category_service = CategoryService(categories_config)

        self._load_enrichment()

        self._intelligence_controller = IntelligenceScanController(
            self._intelligence_cache,
            self.duplicate_service,
            self.smart_category_service,
            self.projections_path,
            parent=self,
        )
        self._receipt_controller = ReceiptMatchController(
            self.event_store,
            self.es_service,
            parent_widget=self,
        )
        self._mutation_controller = TransactionMutationController(
            self.event_store,
            self.es_service,
            self.smart_category_service,
            self.service,
            self.duplicate_service,
            parent_widget=self,
        )

        self._init_ui()
        self._connect_signals()

        from PySide6.QtWidgets import QApplication

        app = QApplication.instance()
        if app:
            app.aboutToQuit.connect(self._intelligence_controller.stop)

        self.reload_transactions()

    def _load_enrichment(self):
        """Load enrichment data from event store."""
        if not self.event_store:
            return
        try:
            events = self.event_store.get_events_by_type("TransactionEnriched")
            self.enrichment_service = EnrichmentService(events)
        except DATA_IO_ERRORS as e:
            logger.warning("Enrichment data unavailable: %s", e)
            self.enrichment_service = None

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        filter_group = self._create_filter_controls()
        layout.addWidget(filter_group, 0)

        self._splitter = QSplitter(Qt.Orientation.Horizontal, self)

        self.table = TransactionTableWidget(self)
        self._splitter.addWidget(self.table)

        self.detail_panel = TransactionDetailPanel(self)
        self._splitter.addWidget(self.detail_panel)
        self.detail_panel.setVisible(False)

        self._splitter.setStretchFactor(0, 3)
        self._splitter.setStretchFactor(1, 1)

        layout.addWidget(self._splitter, 1)

        self._update_status()

        all_cats = []
        for c in self.category_service.load_all_categories():
            all_cats.append(c.name)
            for sub in c.subcategories:
                all_cats.append(f"{c.name}: {sub.name}")
        self.table.set_categories(all_cats)

        if self.enrichment_service:
            self.table.transaction_model.set_enrichment_service(self.enrichment_service)

    def _create_account_and_date_row(self) -> QHBoxLayout:
        """Row 1: account combo, date range combo, custom date edits."""
        row1 = QHBoxLayout()

        row1.addWidget(QLabel("Account:"))
        self.account_combo = QComboBox()
        self.account_combo.addItem("All Accounts", None)
        row1.addWidget(self.account_combo)

        row1.addSpacing(20)

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
        return row1

    def _create_search_and_category_row(self) -> QHBoxLayout:
        """Row 2: search edit, category combo, uncategorized checkbox, status label."""
        row2 = QHBoxLayout()

        row2.addWidget(QLabel("Search:"))
        self.search_edit = QLineEdit()
        self.search_edit.setPlaceholderText("Search description...")
        row2.addWidget(self.search_edit)

        row2.addSpacing(20)

        row2.addWidget(QLabel("Category:"))
        self.category_combo = QComboBox()
        self.category_combo.addItem("All Categories", None)
        row2.addWidget(self.category_combo)

        row2.addSpacing(20)

        self.uncategorized_check = QCheckBox("Show only uncategorized")
        row2.addWidget(self.uncategorized_check)

        row2.addStretch()

        self.status_label = QLabel()
        self.status_label.setStyleSheet("color: gray;")
        row2.addWidget(self.status_label)

        return row2

    def _create_utility_buttons_row(self) -> QHBoxLayout:
        """Row 3: clear, reload, rescan, match receipts buttons."""
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
        return row3

    def _create_filter_controls(self) -> QGroupBox:
        """Create the filter controls group."""
        group = QGroupBox("Filters")
        layout = QVBoxLayout(group)

        layout.addLayout(self._create_account_and_date_row())
        layout.addLayout(self._create_search_and_category_row())
        layout.addLayout(self._create_utility_buttons_row())

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

        if preset == "Custom":
            self._set_custom_dates_visible(True)
            return

        self._set_custom_dates_visible(False)

        if preset == "All":
            self.run_filters()
            return

        today = QDate.currentDate()
        today_py = date(today.year(), today.month(), today.day())
        start, end = get_date_range(preset, today_py)

        if start is None:
            return

        self.start_date_edit.setDate(QDate(start.year, start.month, start.day))
        self.end_date_edit.setDate(QDate(end.year, end.month, end.day))
        self.run_filters()

    def _connect_signals(self):
        """Connect signals to slots."""
        self.clear_btn.clicked.connect(self.clear_filters)
        self.reload_btn.clicked.connect(self.reload_transactions)
        self.rescan_btn.clicked.connect(self._rescan_intelligence)

        self.account_combo.currentIndexChanged.connect(self.run_filters)
        self.date_range_combo.currentIndexChanged.connect(self._on_date_range_changed)
        self.start_date_edit.dateChanged.connect(self.run_filters)
        self.end_date_edit.dateChanged.connect(self.run_filters)
        self.category_combo.currentIndexChanged.connect(self.run_filters)
        self.uncategorized_check.stateChanged.connect(self.run_filters)
        self.search_edit.textChanged.connect(self.run_filters)

        self.table.selection_changed.connect(self._update_status)
        self.table.selection_changed.connect(self._on_selection_changed)

        self.table.categorize_requested.connect(self._on_categorize_requested)
        self.table.apply_prediction_requested.connect(self._mutation_controller._run_prediction)
        self.table.note_requested.connect(self._on_note_requested)
        self.table.duplicate_resolution_requested.connect(self._on_resolve_duplicate_requested)
        self.table.manual_merge_requested.connect(self._on_manual_merge_requested)
        self.table.receipt_match_requested.connect(self._on_receipt_match_requested)
        self.detail_panel.receipt_match_requested.connect(self._on_receipt_match_requested)
        self.detail_panel.apply_prediction_requested.connect(
            self._mutation_controller._run_prediction
        )
        self.detail_panel.apply_receipt_requested.connect(
            self._receipt_controller.run_match_from_panel
        )
        self.match_receipts_btn.clicked.connect(self._on_batch_receipt_match)

        self._mutation_controller.data_changed.connect(self._on_mutation_data_changed)
        self._mutation_controller.status_message.connect(self.status_message.emit)
        self._receipt_controller.data_changed.connect(self._on_receipt_data_changed)
        self._receipt_controller.status_message.connect(self.status_message.emit)
        self._intelligence_controller.status_message.connect(self.status_message.emit)
        self._intelligence_controller.scan_started.connect(self.scan_started.emit)
        self._intelligence_controller.scan_progress.connect(self.scan_progress.emit)
        self._intelligence_controller.scan_finished.connect(self.scan_finished.emit)
        self._intelligence_controller.scan_finished.connect(self._update_status)
        self._intelligence_controller.metadata_updated.connect(
            self.table.transaction_model.update_metadata
        )
        self._intelligence_controller.metadata_cleared.connect(
            self.table.transaction_model.clear_metadata
        )

        self.table.transaction_model.transaction_updated.connect(
            self._mutation_controller.on_transaction_updated
        )

    def reload_transactions(self, restore_transaction_id: str | None = None):
        """Reload all transactions from disk.

        Args:
            restore_transaction_id: If provided, re-select this transaction after reload.
        """
        self._load_enrichment()
        if self.enrichment_service:
            self.table.transaction_model.set_enrichment_service(self.enrichment_service)

        self.service.clear_cache()

        self.table.reset()

        self._all_transactions = self.service.load_all_transactions()
        self.table.set_all_transactions(self._all_transactions)

        self._update_account_combo()
        self._update_category_combo()

        self.run_filters()

        if restore_transaction_id:
            self.table.select_transaction_by_id(restore_transaction_id)

        self.transactions_loaded.emit(len(self._all_transactions))

        self._intelligence_controller.start_scan(self._all_transactions)

    def _rescan_intelligence(self):
        """Delegate intelligence rescan to the controller."""
        self._intelligence_controller.rescan(self._all_transactions)

    def _on_categorize_requested(self):
        """Bridge: get selected transactions and delegate to mutation controller."""
        self._mutation_controller.categorize_selected(self.table.get_selected_transactions())

    def _on_note_requested(self):
        """Bridge: get selected transactions and delegate to mutation controller."""
        self._mutation_controller.note_selected(self.table.get_selected_transactions())

    def _on_resolve_duplicate_requested(self):
        """Bridge: get selected transaction with metadata and delegate to mutation controller."""
        selected = self.table.get_selected_transactions()
        if len(selected) != 1:
            return
        meta = self.table.transaction_model.get_metadata(selected[0].primary.transaction_id)
        self._mutation_controller.run_duplicate_resolution(selected[0], meta)

    def _on_manual_merge_requested(self):
        """Bridge: get selected transactions and delegate to mutation controller."""
        self._mutation_controller.manual_merge(self.table.get_selected_transactions())

    def _on_receipt_match_requested(self):
        """Bridge: get selected transactions and delegate to receipt controller."""
        self._receipt_controller.run_single_match(self.table.get_selected_transactions())

    def _on_batch_receipt_match(self):
        """Bridge: delegate batch receipt match to receipt controller."""
        self._receipt_controller.run_batch_match(self._all_transactions, self.enrichment_service)

    def _on_mutation_data_changed(self, restore_id):
        """Reload transactions after a mutation, optionally restoring selection."""
        self.reload_transactions(restore_transaction_id=restore_id)

    def _on_receipt_data_changed(self, restore_id):
        """Reload transactions after a receipt match, optionally restoring selection."""
        self.reload_transactions(restore_transaction_id=restore_id)

    def _update_account_combo(self):
        """Update the account combo box with available accounts."""
        current = self.account_combo.currentData()

        self.account_combo.clear()
        self.account_combo.addItem("All Accounts", None)

        accounts = self.service.load_available_accounts()
        for account_id in accounts:
            self.account_combo.addItem(account_id, account_id)

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

        if current:
            index = self.category_combo.findData(current)
            if index >= 0:
                self.category_combo.setCurrentIndex(index)

    def run_filters(self):
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
        self.date_range_combo.setCurrentIndex(0)
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
            metadata = self.table.transaction_model.get_metadata(txn.primary.transaction_id)
            if not enrichment:
                receipt_candidates = self._receipt_controller.find_candidates(txn)
        self.detail_panel.update_transaction(txn, enrichment, metadata, receipt_candidates)

    def toggle_detail_panel(self):
        """Toggle the detail panel visibility."""
        visible = not self.detail_panel.isVisible()
        self.detail_panel.setVisible(visible)
        if visible:
            self._on_selection_changed()
