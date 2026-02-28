from __future__ import annotations

"""
Transaction Table Model - Qt model for displaying transactions

Provides data to QTableView for transaction display with sorting and formatting.
"""

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt, Signal

from gilt.gui.services.enrichment_service import EnrichmentService
from gilt.gui.theme import Theme
from gilt.model.account import TransactionGroup


class TransactionTableModel(QAbstractTableModel):
    """Table model for displaying transaction data."""

    # Signal emitted when a transaction is updated via the model
    transaction_updated = Signal(object)  # TransactionGroup

    # Column definitions
    COLUMNS = [
        "Date",
        "Account",
        "Description",
        "Amount",
        "Currency",
        "Category",
        "Subcategory",
        "Notes",
        "Transfer",
        "Risk",
        "Conf.",
    ]

    # Column indices
    COL_DATE = 0
    COL_ACCOUNT = 1
    COL_DESCRIPTION = 2
    COL_AMOUNT = 3
    COL_CURRENCY = 4
    COL_CATEGORY = 5
    COL_SUBCATEGORY = 6
    COL_NOTES = 7
    COL_TRANSFER = 8
    COL_RISK = 9
    COL_CONFIDENCE = 10

    # Custom roles
    SortRole = Qt.ItemDataRole.UserRole + 1

    def __init__(self, parent=None):
        super().__init__(parent)
        self._transactions: list[TransactionGroup] = []
        self._metadata_cache: dict[str, dict] = {}  # txn_id -> {risk: bool, confidence: float}
        self._enrichment_service: EnrichmentService | None = None

    def set_enrichment_service(self, service: EnrichmentService | None):
        """Set the enrichment service for displaying enriched descriptions."""
        self._enrichment_service = service
        self.layoutChanged.emit()

    def update_metadata(self, metadata: dict[str, dict]):
        """Update metadata cache and refresh view."""
        self._metadata_cache.update(metadata)
        # Emit dataChanged for all rows (simplest, though could be optimized)
        self.layoutChanged.emit()

    def get_metadata(self, transaction_id: str) -> dict:
        """Get metadata for a transaction."""
        return self._metadata_cache.get(transaction_id, {})

    def rowCount(self, parent=QModelIndex()):
        """Return number of rows (transactions)."""
        if parent.isValid():
            return 0
        return len(self._transactions)

    def columnCount(self, parent=QModelIndex()):
        """Return number of columns."""
        if parent.isValid():
            return 0
        return len(self.COLUMNS)

    def data(self, index: QModelIndex, role=Qt.DisplayRole):
        """Return data for the given index and role."""
        if not index.isValid():
            return None

        if index.row() >= len(self._transactions):
            return None

        group = self._transactions[index.row()]
        txn = group.primary
        col = index.column()

        # Display role - what text to show
        if role == Qt.DisplayRole:
            if col == self.COL_DATE:
                return str(txn.date)
            elif col == self.COL_ACCOUNT:
                return txn.account_id
            elif col == self.COL_DESCRIPTION:
                if self._enrichment_service:
                    enriched = self._enrichment_service.get_display_description(txn.transaction_id)
                    if enriched:
                        return enriched
                return txn.description or ""
            elif col == self.COL_AMOUNT:
                return f"{txn.amount:.2f}"
            elif col == self.COL_CURRENCY:
                return txn.currency or "CAD"
            elif col == self.COL_CATEGORY:
                return txn.category or ""
            elif col == self.COL_SUBCATEGORY:
                return txn.subcategory or ""
            elif col == self.COL_NOTES:
                return txn.notes or ""
            elif col == self.COL_TRANSFER:
                # Check if transaction has transfer metadata
                if txn.metadata and "transfer" in txn.metadata:
                    transfer = txn.metadata["transfer"]
                    transfer_role = transfer.get("role", "")
                    method = transfer.get("method", "")
                    return f"{transfer_role} ({method})" if transfer_role else ""
                return ""
            elif col == self.COL_RISK:
                meta = self._metadata_cache.get(txn.transaction_id, {})
                return "⚠️" if meta.get("risk") else ""
            elif col == self.COL_CONFIDENCE:
                meta = self._metadata_cache.get(txn.transaction_id, {})
                conf = meta.get("confidence")
                return f"{conf:.0%}" if conf is not None else ""

        # Sort role - raw data for sorting
        elif role == self.SortRole:
            if col == self.COL_DATE:
                return txn.date
            elif col == self.COL_AMOUNT:
                return txn.amount
            elif col == self.COL_CONFIDENCE:
                meta = self._metadata_cache.get(txn.transaction_id, {})
                return meta.get("confidence", 0.0)
            elif col == self.COL_RISK:
                meta = self._metadata_cache.get(txn.transaction_id, {})
                return 1 if meta.get("risk") else 0
            else:
                # Fallback to string representation for other columns
                return self.data(index, Qt.DisplayRole)

        # Text alignment
        elif role == Qt.TextAlignmentRole:
            if col == self.COL_AMOUNT or col == self.COL_CONFIDENCE:
                return Qt.AlignRight | Qt.AlignVCenter
            elif col == self.COL_RISK:
                return Qt.AlignCenter

        # Tooltip role
        elif role == Qt.ToolTipRole:
            if col == self.COL_RISK:
                meta = self._metadata_cache.get(txn.transaction_id, {})
                if meta.get("risk"):
                    return "Potential duplicate detected"
            elif (
                col == self.COL_CONFIDENCE
                or col == self.COL_CATEGORY
                or col == self.COL_SUBCATEGORY
            ):
                meta = self._metadata_cache.get(txn.transaction_id, {})
                conf = meta.get("confidence")
                if conf is not None:
                    return f"Categorization confidence: {conf:.1%}"

        # Background color role for low confidence
        elif role == Qt.BackgroundRole:
            if col == self.COL_CATEGORY or col == self.COL_SUBCATEGORY:
                meta = self._metadata_cache.get(txn.transaction_id, {})
                conf = meta.get("confidence")
                if conf is not None and conf < 0.8:
                    return Theme.color("warning_bg")
            return None

        # Foreground color (text color)
        elif role == Qt.ForegroundRole:
            if col == self.COL_CATEGORY or col == self.COL_SUBCATEGORY:
                meta = self._metadata_cache.get(txn.transaction_id, {})
                conf = meta.get("confidence")
                if conf is not None and conf < 0.8:
                    return Theme.color("warning_fg")

            if col == self.COL_DESCRIPTION and self._enrichment_service and self._enrichment_service.is_enriched(
                txn.transaction_id
            ):
                return Theme.color("link_fg")

            if col == self.COL_AMOUNT:
                if txn.amount < 0:
                    return Theme.color("negative_fg")
                elif txn.amount > 0:
                    return Theme.color("positive_fg")
                else:
                    return Theme.color("neutral_fg")
            elif col == self.COL_TRANSFER and txn.metadata and "transfer" in txn.metadata:
                return Theme.color("link_fg")

        # Tooltip
        elif role == Qt.ToolTipRole:
            if col == self.COL_DATE:
                return f"Transaction ID: {txn.transaction_id[:8]}"
            elif col == self.COL_DESCRIPTION:
                tooltip = txn.description or ""
                if self._enrichment_service and self._enrichment_service.is_enriched(
                    txn.transaction_id
                ):
                    enrichment = self._enrichment_service.get_enrichment(txn.transaction_id)
                    tooltip = f"Bank: {txn.description}"
                    tooltip += f"\nVendor: {enrichment.vendor}"
                    if enrichment.service:
                        tooltip += f"\nService: {enrichment.service}"
                if txn.counterparty and txn.counterparty != txn.description:
                    tooltip += f"\nCounterparty: {txn.counterparty}"
                if txn.source_file:
                    tooltip += f"\nSource: {txn.source_file}"
                return tooltip
            elif col == self.COL_TRANSFER and txn.metadata and "transfer" in txn.metadata:
                transfer = txn.metadata["transfer"]
                lines = []
                if "role" in transfer:
                    lines.append(f"Role: {transfer['role']}")
                if "counterparty_account_id" in transfer:
                    lines.append(f"Counterparty: {transfer['counterparty_account_id']}")
                if "method" in transfer:
                    lines.append(f"Method: {transfer['method']}")
                return "\n".join(lines)

        return None

    def headerData(self, section, orientation, role=Qt.DisplayRole):
        """Return header data."""
        if role == Qt.DisplayRole:
            if orientation == Qt.Horizontal:
                if 0 <= section < len(self.COLUMNS):
                    return self.COLUMNS[section]
            elif orientation == Qt.Vertical:
                return str(section + 1)
        return None

    def flags(self, index: QModelIndex):
        """Return item flags (enabled, selectable)."""
        if not index.isValid():
            return Qt.NoItemFlags

        flags = Qt.ItemIsEnabled | Qt.ItemIsSelectable

        if index.column() == self.COL_CATEGORY:
            flags |= Qt.ItemIsEditable

        return flags

    def setData(self, index: QModelIndex, value, role=Qt.EditRole):
        """Set data for the given index and role."""
        if not index.isValid() or role != Qt.EditRole:
            return False

        if index.column() == self.COL_CATEGORY:
            group = self._transactions[index.row()]
            txn = group.primary

            # Handle "Category: Subcategory" format
            new_category = value
            new_subcategory = None

            if value and ":" in value:
                parts = value.split(":", 1)
                new_category = parts[0].strip()
                new_subcategory = parts[1].strip()

            if txn.category != new_category or txn.subcategory != new_subcategory:
                txn.category = new_category
                txn.subcategory = new_subcategory

                # Emit dataChanged for both Category and Subcategory columns
                self.dataChanged.emit(index, index, [Qt.DisplayRole, Qt.EditRole])

                # Also update subcategory column
                subcat_index = index.sibling(index.row(), self.COL_SUBCATEGORY)
                self.dataChanged.emit(subcat_index, subcat_index, [Qt.DisplayRole])

                # Notify listeners (View) to persist changes
                self.transaction_updated.emit(group)
                return True

        return False

    def update_transactions(self, transactions: list[TransactionGroup]):
        """Update the model with new transaction data."""
        self.beginResetModel()
        self._transactions = transactions
        self.endResetModel()

    def get_transaction(self, row: int) -> TransactionGroup | None:
        """Get transaction group at the specified row."""
        if 0 <= row < len(self._transactions):
            return self._transactions[row]
        return None

    def clear(self):
        """Clear all transactions from the model."""
        self.beginResetModel()
        self._transactions = []
        self.endResetModel()
