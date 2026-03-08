from __future__ import annotations

"""
Transaction Sort/Filter Proxy Model

Custom proxy model that handles both sorting and filtering of transactions.
The source model always holds the full transaction list; this proxy controls
what is visible based on filter criteria.
"""

from datetime import date

from PySide6.QtCore import QModelIndex, QSortFilterProxyModel, Qt

from gilt.gui.models.transaction_model import TransactionTableModel


class TransactionSortFilterProxyModel(QSortFilterProxyModel):
    """Proxy model that sorts and filters transactions."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setSortRole(TransactionTableModel.SortRole)
        self.setDynamicSortFilter(True)
        self.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.setFilterKeyColumn(-1)

        # Filter criteria
        self._account_filter: list[str] | None = None
        self._start_date: date | None = None
        self._end_date: date | None = None
        self._category_filter: list[str] | None = None
        self._search_text: str | None = None
        self._uncategorized_only: bool = False

    def set_filters(
        self,
        account_filter: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        category_filter: list[str] | None = None,
        search_text: str | None = None,
        uncategorized_only: bool = False,
    ):
        """Update all filter criteria and re-filter."""
        self._account_filter = account_filter
        self._start_date = start_date
        self._end_date = end_date
        self._category_filter = category_filter
        self._search_text = search_text.lower() if search_text else None
        self._uncategorized_only = uncategorized_only
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row: int, source_parent: QModelIndex) -> bool:
        """Return True if the row passes all active filters."""
        model = self.sourceModel()
        txn_group = model.get_transaction(source_row)
        if txn_group is None:
            return False

        txn = txn_group.primary

        if self._account_filter and txn.account_id not in self._account_filter:
            return False

        if self._start_date and txn.date < self._start_date:
            return False

        if self._end_date and txn.date > self._end_date:
            return False

        if self._category_filter and txn.category not in self._category_filter:
            return False

        if self._uncategorized_only and txn.category:
            return False

        if self._search_text:
            desc = (txn.description or "").lower()
            if self._search_text not in desc:
                return False

        return True

    def lessThan(self, left, right):
        """Compare two items for sorting."""
        left_data = self.sourceModel().data(left, self.sortRole())
        right_data = self.sourceModel().data(right, self.sortRole())

        if left_data is None:
            return True
        if right_data is None:
            return False

        try:
            return left_data < right_data
        except TypeError:
            return str(left_data) < str(right_data)
