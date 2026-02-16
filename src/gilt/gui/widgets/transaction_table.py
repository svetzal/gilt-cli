from __future__ import annotations

"""
Transaction Table Widget - Enhanced table view for transactions

Custom table widget with sorting, selection, and formatting capabilities.
"""

from PySide6.QtWidgets import QTableView, QHeaderView, QMenu
from PySide6.QtCore import Qt, Signal, QPoint

from gilt.gui.models.transaction_model import TransactionTableModel
from gilt.gui.models.transaction_proxy_model import TransactionSortFilterProxyModel
from gilt.gui.delegates.category_delegate import CategoryDelegate
from gilt.model.account import TransactionGroup


class TransactionTableWidget(QTableView):
    """Enhanced table view for displaying transactions."""

    # Signal emitted when selection changes
    selection_changed = Signal()

    # Signals for context menu actions
    categorize_requested = Signal()  # User wants to categorize selected transactions
    note_requested = Signal()  # User wants to add/edit note on selected transaction
    duplicate_resolution_requested = Signal()  # User wants to resolve duplicate
    manual_merge_requested = Signal()  # User wants to merge two selected transactions

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create model
        self._model = TransactionTableModel(self)

        # Create proxy model for sorting
        self._proxy = TransactionSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        # Set the proxy as the view's model
        self.setModel(self._proxy)

        # Configure table appearance
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectionBehavior.SelectRows)
        self.setSelectionMode(QTableView.SelectionMode.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)

        # Configure horizontal header
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        # Make all columns interactively resizable by user
        header.setSectionResizeMode(QHeaderView.ResizeMode.Interactive)

        # Set initial default widths for better UX
        header.resizeSection(TransactionTableModel.COL_DATE, 100)
        header.resizeSection(TransactionTableModel.COL_ACCOUNT, 120)
        header.resizeSection(TransactionTableModel.COL_DESCRIPTION, 300)
        header.resizeSection(TransactionTableModel.COL_AMOUNT, 100)
        header.resizeSection(TransactionTableModel.COL_CURRENCY, 80)
        header.resizeSection(TransactionTableModel.COL_CATEGORY, 120)
        header.resizeSection(TransactionTableModel.COL_SUBCATEGORY, 120)
        header.resizeSection(TransactionTableModel.COL_NOTES, 200)
        header.resizeSection(TransactionTableModel.COL_TRANSFER, 100)
        header.resizeSection(TransactionTableModel.COL_RISK, 50)
        header.resizeSection(TransactionTableModel.COL_CONFIDENCE, 60)

        # Connect signals
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Enable context menu
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _on_selection_changed(self):
        """Handle selection change."""
        self.selection_changed.emit()

    def update_transactions(self, transactions: list[TransactionGroup]):
        """
        Update the table with new transaction data.

        Args:
            transactions: List of transaction groups to display
        """
        self._model.update_transactions(transactions)

        # Reset sorting to default (date descending)
        self.sortByColumn(TransactionTableModel.COL_DATE, Qt.SortOrder.DescendingOrder)

    def get_selected_transactions(self) -> list[TransactionGroup]:
        """
        Get currently selected transactions.

        Returns:
            List of selected transaction groups
        """
        selected = []
        for index in self.selectionModel().selectedRows():
            # Map proxy index to source model index
            source_index = self._proxy.mapToSource(index)
            txn = self._model.get_transaction(source_index.row())
            if txn:
                selected.append(txn)
        return selected

    def clear(self):
        """Clear all transactions from the table."""
        self._model.clear()

    def get_row_count(self) -> int:
        """Get the number of rows currently displayed (after filtering/sorting)."""
        return self._proxy.rowCount()

    def get_total_count(self) -> int:
        """Get the total number of transactions in the model."""
        return self._model.rowCount()

    def _show_context_menu(self, position: QPoint):
        """
        Show context menu at the specified position.

        Args:
            position: Position where the menu should be shown
        """
        selected = self.get_selected_transactions()
        if not selected:
            return

        menu = QMenu(self)

        # Categorize action
        categorize_action = menu.addAction("Categorize...")
        categorize_action.triggered.connect(self.categorize_requested.emit)

        # Note action (only for single selection)
        if len(selected) == 1:
            note_action = menu.addAction("Edit Note...")
            note_action.triggered.connect(self.note_requested.emit)

            # Check for duplicate risk
            txn = selected[0].primary
            meta = self._model.get_metadata(txn.transaction_id)
            if meta.get("risk"):
                menu.addSeparator()
                resolve_action = menu.addAction("Resolve Duplicate...")
                resolve_action.triggered.connect(self.duplicate_resolution_requested.emit)

        # Manual merge action (for exactly two selections)
        if len(selected) == 2:
            menu.addSeparator()
            merge_action = menu.addAction("Mark as Duplicate...")
            merge_action.triggered.connect(self.manual_merge_requested.emit)

        menu.addSeparator()

        # Copy transaction ID
        if len(selected) == 1:
            copy_action = menu.addAction("Copy Transaction ID")
            # Capture ID string to avoid keeping object reference
            txn_id = selected[0].primary.transaction_id
            copy_action.triggered.connect(lambda: self._copy_transaction_id_str(txn_id))

        # Show menu
        # Map position from widget coordinates to global
        menu.exec(self.mapToGlobal(position))

    def _copy_transaction_id_str(self, transaction_id: str):
        """
        Copy transaction ID to clipboard.

        Args:
            transaction_id: Transaction ID string
        """
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(transaction_id)

    def _copy_transaction_id(self, transaction: TransactionGroup):
        """Deprecated: Use _copy_transaction_id_str instead."""
        self._copy_transaction_id_str(transaction.primary.transaction_id)

    @property
    def transaction_model(self) -> TransactionTableModel:
        """Get the underlying transaction model."""
        return self._model

    def set_categories(self, categories: list[str]):
        """Set available categories for the delegate."""
        delegate = CategoryDelegate(self, categories)
        self.setItemDelegateForColumn(TransactionTableModel.COL_CATEGORY, delegate)
