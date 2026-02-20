from __future__ import annotations

"""
Transaction Sort/Filter Proxy Model

Custom proxy model for sorting transactions. Uses the custom SortRole from
TransactionTableModel to ensure correct sorting of numeric and date types.
"""

from PySide6.QtCore import QSortFilterProxyModel, Qt

from gilt.gui.models.transaction_model import TransactionTableModel


class TransactionSortFilterProxyModel(QSortFilterProxyModel):
    """Custom proxy model for sorting transactions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(TransactionTableModel.SortRole)
        self.setDynamicSortFilter(False)  # Only sort when explicitly requested
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)  # Filter all columns

    def lessThan(self, left, right):
        """Compare two items for sorting."""
        # Get raw data using SortRole
        left_data = self.sourceModel().data(left, self.sortRole())
        right_data = self.sourceModel().data(right, self.sortRole())

        # Handle None values (treat as smallest)
        if left_data is None:
            return True
        if right_data is None:
            return False

        try:
            return left_data < right_data
        except TypeError:
            # Fallback for incompatible types
            return str(left_data) < str(right_data)
