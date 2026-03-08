from __future__ import annotations

"""
Transaction Detail Panel - Inline panel showing transaction details.

Displays transaction information in a side panel within the transactions view,
replacing the modal dialog approach. Updates automatically when selection changes.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFormLayout,
    QGroupBox,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from gilt.gui.services.enrichment_service import EnrichmentData
from gilt.model.account import TransactionGroup


class TransactionDetailPanel(QScrollArea):
    """Scrollable side panel that shows details for the selected transaction."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        self.setMinimumWidth(280)

        self._container = QWidget()
        self._layout = QVBoxLayout(self._container)
        self._layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.setWidget(self._container)

        self._show_placeholder()

    def update_transaction(
        self,
        transaction: TransactionGroup | None,
        enrichment: EnrichmentData | None = None,
    ):
        """Update the panel to show details for the given transaction."""
        self._clear()

        if transaction is None:
            self._show_placeholder()
            return

        txn = transaction.primary

        self._layout.addWidget(self._build_basics_section(txn))

        if enrichment:
            self._layout.addWidget(self._build_enrichment_section(enrichment, txn.currency))

        if txn.metadata and "transfer" in txn.metadata:
            self._layout.addWidget(self._build_transfer_section(txn.metadata["transfer"]))

        self._layout.addStretch()

    def _clear(self):
        """Remove all widgets from the layout."""
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

    def _show_placeholder(self):
        """Show placeholder text when no transaction is selected."""
        label = QLabel("Select a transaction to view details")
        label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        label.setWordWrap(True)
        label.setStyleSheet("color: gray; padding: 20px;")
        self._layout.addWidget(label)
        self._layout.addStretch()

    def _build_basics_section(self, txn) -> QGroupBox:
        """Build the transaction basics group box."""
        group = QGroupBox("Transaction")
        form = QFormLayout(group)
        form.addRow("Transaction ID:", self._label(txn.transaction_id))
        form.addRow("Date:", self._label(str(txn.date)))
        form.addRow("Account:", self._label(txn.account_id))
        form.addRow("Description:", self._label(txn.description or ""))
        form.addRow("Amount:", self._label(f"{txn.amount:.2f} {txn.currency or 'CAD'}"))
        if txn.category:
            cat_text = txn.category
            if txn.subcategory:
                cat_text += f": {txn.subcategory}"
            form.addRow("Category:", self._label(cat_text))
        if txn.counterparty:
            form.addRow("Counterparty:", self._label(txn.counterparty))
        if txn.notes:
            form.addRow("Notes:", self._label(txn.notes))
        if txn.source_file:
            form.addRow("Source file:", self._label(txn.source_file))
        return group

    def _build_enrichment_section(
        self, enrichment: EnrichmentData, txn_currency: str | None
    ) -> QGroupBox:
        """Build the receipt enrichment group box."""
        group = QGroupBox("Receipt Enrichment")
        form = QFormLayout(group)
        form.addRow("Vendor:", self._label(enrichment.vendor))
        if enrichment.service:
            form.addRow("Service:", self._label(enrichment.service))
        if enrichment.invoice_number:
            form.addRow("Invoice #:", self._label(enrichment.invoice_number))
        if enrichment.tax_amount is not None:
            tax_text = f"{enrichment.tax_amount}"
            if enrichment.tax_type:
                tax_text += f" ({enrichment.tax_type})"
            form.addRow("Tax:", self._label(tax_text))
        if enrichment.currency and enrichment.currency != (txn_currency or "CAD"):
            form.addRow("Receipt currency:", self._label(enrichment.currency))
        if enrichment.receipt_file:
            form.addRow("Receipt PDF:", self._label(enrichment.receipt_file))
        if enrichment.source_email:
            form.addRow("Source email:", self._label(enrichment.source_email))
        if enrichment.match_confidence:
            form.addRow("Match confidence:", self._label(enrichment.match_confidence))
        return group

    def _build_transfer_section(self, transfer: dict) -> QGroupBox:
        """Build the transfer link group box."""
        group = QGroupBox("Transfer Link")
        form = QFormLayout(group)
        if "role" in transfer:
            form.addRow("Role:", self._label(transfer["role"]))
        if "counterparty_account_id" in transfer:
            form.addRow("Counterparty account:", self._label(transfer["counterparty_account_id"]))
        if "method" in transfer:
            form.addRow("Method:", self._label(transfer["method"]))
        return group

    def _label(self, text: str) -> QLabel:
        """Create a selectable label for form values."""
        label = QLabel(text)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        return label
