from __future__ import annotations

"""
Transaction Table Widget - Enhanced table view for transactions

Custom table widget with sorting, selection, and formatting capabilities.
"""

from PySide6.QtWidgets import QTableView, QHeaderView, QMenu
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel, QPoint
from PySide6.QtGui import QAction

from finance.gui.models.transaction_model import TransactionTableModel
from finance.model.account import TransactionGroup


class TransactionTableWidget(QTableView):
    """Enhanced table view for displaying transactions."""

    # Signal emitted when selection changes
    selection_changed = Signal()

    # Signals for context menu actions
    categorize_requested = Signal()  # User wants to categorize selected transactions
    note_requested = Signal()  # User wants to add/edit note on selected transaction

    def __init__(self, parent=None):
        super().__init__(parent)

        # Create model
        self._model = TransactionTableModel(self)

        # Create proxy model for sorting
        self._proxy = QSortFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        # Set the proxy as the view's model
        self.setModel(self._proxy)

        # Configure table appearance
        self.setAlternatingRowColors(True)
        self.setSelectionBehavior(QTableView.SelectRows)
        self.setSelectionMode(QTableView.ExtendedSelection)
        self.setSortingEnabled(True)
        self.setShowGrid(False)
        self.verticalHeader().setVisible(False)

        # Configure horizontal header
        header = self.horizontalHeader()
        header.setStretchLastSection(True)
        # Make all columns interactively resizable by user
        header.setSectionResizeMode(QHeaderView.Interactive)

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

        # Connect signals
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

        # Enable context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
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
        self.sortByColumn(
            TransactionTableModel.COL_DATE, Qt.DescendingOrder
        )

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
        categorize_action = QAction("Categorize...", self)
        categorize_action.triggered.connect(self.categorize_requested.emit)
        menu.addAction(categorize_action)

        # Note action (only for single selection)
        if len(selected) == 1:
            note_action = QAction("Edit Note...", self)
            note_action.triggered.connect(self.note_requested.emit)
            menu.addAction(note_action)

        menu.addSeparator()

        # Copy transaction ID
        if len(selected) == 1:
            copy_action = QAction("Copy Transaction ID", self)
            copy_action.triggered.connect(
                lambda: self._copy_transaction_id(selected[0])
            )
            menu.addAction(copy_action)

        # Show menu
        menu.exec(self.viewport().mapToGlobal(position))

    def _copy_transaction_id(self, transaction: TransactionGroup):
        """
        Copy transaction ID to clipboard.

        Args:
            transaction: Transaction group
        """
        from PySide6.QtWidgets import QApplication

        clipboard = QApplication.clipboard()
        clipboard.setText(transaction.primary.transaction_id)
