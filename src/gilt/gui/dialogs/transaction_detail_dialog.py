from __future__ import annotations

"""
Transaction Detail Dialog - Shows full transaction details on double-click.

Displays the raw bank description and, if receipt enrichment exists,
vendor name, product/service, tax breakdown, receipt file path, etc.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QFormLayout,
    QLabel,
    QGroupBox,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt

from gilt.model.account import TransactionGroup
from gilt.gui.services.enrichment_service import EnrichmentData


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

        # Transaction basics
        basics_group = QGroupBox("Transaction")
        basics_form = QFormLayout(basics_group)
        basics_form.addRow("Transaction ID:", self._label(txn.transaction_id))
        basics_form.addRow("Date:", self._label(str(txn.date)))
        basics_form.addRow("Account:", self._label(txn.account_id))
        basics_form.addRow("Description:", self._label(txn.description or ""))
        basics_form.addRow("Amount:", self._label(f"{txn.amount:.2f} {txn.currency or 'CAD'}"))
        if txn.category:
            cat_text = txn.category
            if txn.subcategory:
                cat_text += f": {txn.subcategory}"
            basics_form.addRow("Category:", self._label(cat_text))
        if txn.counterparty:
            basics_form.addRow("Counterparty:", self._label(txn.counterparty))
        if txn.notes:
            basics_form.addRow("Notes:", self._label(txn.notes))
        if txn.source_file:
            basics_form.addRow("Source file:", self._label(txn.source_file))
        layout.addWidget(basics_group)

        # Enrichment data (from receipt matching)
        if enrichment:
            enrichment_group = QGroupBox("Receipt Enrichment")
            enrichment_form = QFormLayout(enrichment_group)
            enrichment_form.addRow("Vendor:", self._label(enrichment.vendor))
            if enrichment.service:
                enrichment_form.addRow("Service:", self._label(enrichment.service))
            if enrichment.invoice_number:
                enrichment_form.addRow("Invoice #:", self._label(enrichment.invoice_number))
            if enrichment.tax_amount is not None:
                tax_text = f"{enrichment.tax_amount}"
                if enrichment.tax_type:
                    tax_text += f" ({enrichment.tax_type})"
                enrichment_form.addRow("Tax:", self._label(tax_text))
            if enrichment.currency and enrichment.currency != (txn.currency or "CAD"):
                enrichment_form.addRow("Receipt currency:", self._label(enrichment.currency))
            if enrichment.receipt_file:
                enrichment_form.addRow("Receipt PDF:", self._label(enrichment.receipt_file))
            if enrichment.source_email:
                enrichment_form.addRow("Source email:", self._label(enrichment.source_email))
            if enrichment.match_confidence:
                enrichment_form.addRow(
                    "Match confidence:", self._label(enrichment.match_confidence)
                )
            layout.addWidget(enrichment_group)

        # Transfer metadata
        if txn.metadata and "transfer" in txn.metadata:
            transfer = txn.metadata["transfer"]
            transfer_group = QGroupBox("Transfer Link")
            transfer_form = QFormLayout(transfer_group)
            if "role" in transfer:
                transfer_form.addRow("Role:", self._label(transfer["role"]))
            if "counterparty_account_id" in transfer:
                transfer_form.addRow(
                    "Counterparty account:", self._label(transfer["counterparty_account_id"])
                )
            if "method" in transfer:
                transfer_form.addRow("Method:", self._label(transfer["method"]))
            layout.addWidget(transfer_group)

        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _label(self, text: str) -> QLabel:
        """Create a selectable label for form values."""
        label = QLabel(text)
        label.setTextInteractionFlags(Qt.TextSelectableByMouse)
        label.setWordWrap(True)
        return label
