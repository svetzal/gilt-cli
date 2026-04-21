from __future__ import annotations

"""
Transaction Detail Dialog - Shows full transaction details on double-click.

Displays the raw bank description and, if receipt enrichment exists,
vendor name, product/service, tax breakdown, receipt file path, etc.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
)

from gilt.gui.services.enrichment_service import EnrichmentData
from gilt.gui.widgets.transaction_sections import (
    build_basics_section,
    build_enrichment_section,
    build_transfer_section,
)
from gilt.model.account import TransactionGroup
from gilt.transfer import TRANSFER_META_KEY


class TransactionDetailDialog(QDialog):
    """Dialog showing full transaction details including enrichment data."""

    def __init__(
        self,
        transaction: TransactionGroup,
        enrichment: EnrichmentData | None = None,
        parent=None,
    ):
        super().__init__(parent)
        self.setWindowTitle("Transaction Details")
        self.setMinimumWidth(500)
        self.setModal(True)
        self._init_ui(transaction, enrichment)

    def _init_ui(self, transaction: TransactionGroup, enrichment: EnrichmentData | None):
        layout = QVBoxLayout(self)
        txn = transaction.primary

        layout.addWidget(self._build_basics_section(txn))

        if enrichment:
            layout.addWidget(self._build_enrichment_section(enrichment, txn.currency))

        if txn.metadata and TRANSFER_META_KEY in txn.metadata:
            layout.addWidget(self._build_transfer_section(txn.metadata[TRANSFER_META_KEY]))

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _build_basics_section(self, txn) -> QGroupBox:
        """Build the transaction basics group box."""
        return build_basics_section(self._label, txn)

    def _build_enrichment_section(
        self, enrichment: EnrichmentData, txn_currency: str | None
    ) -> QGroupBox:
        """Build the receipt enrichment group box."""
        return build_enrichment_section(self._label, enrichment, txn_currency)

    def _build_transfer_section(self, transfer: dict) -> QGroupBox:
        """Build the transfer link group box."""
        return build_transfer_section(self._label, transfer)

    def _label(self, text: str) -> QLabel:
        """Create a selectable label for form values."""
        label = QLabel(text)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setWordWrap(True)
        return label
