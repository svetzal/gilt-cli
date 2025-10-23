from __future__ import annotations

"""
Transaction Table Widget - Enhanced table view for transactions

Custom table widget with sorting, selection, and formatting capabilities.
"""

from PySide6.QtWidgets import QTableView, QHeaderView
from PySide6.QtCore import Qt, Signal, QSortFilterProxyModel

from finance.gui.models.transaction_model import TransactionTableModel
from finance.model.account import TransactionGroup


class TransactionTableWidget(QTableView):
    """Enhanced table view for displaying transactions."""

    # Signal emitted when selection changes
    selection_changed = Signal()

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
        header.setStretchLastSection(False)
        header.setSectionResizeMode(
            TransactionTableModel.COL_DATE, QHeaderView.ResizeToContents
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_ACCOUNT, QHeaderView.ResizeToContents
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_DESCRIPTION, QHeaderView.Stretch
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_AMOUNT, QHeaderView.ResizeToContents
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_CURRENCY, QHeaderView.ResizeToContents
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_CATEGORY, QHeaderView.ResizeToContents
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_SUBCATEGORY, QHeaderView.ResizeToContents
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_NOTES, QHeaderView.Stretch
        )
        header.setSectionResizeMode(
            TransactionTableModel.COL_TRANSFER, QHeaderView.ResizeToContents
        )

        # Connect signals
        self.selectionModel().selectionChanged.connect(self._on_selection_changed)

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
