from __future__ import annotations

"""
Transaction Detail Panel - Inline panel showing transaction details.

Displays transaction information in a side panel within the transactions view,
replacing the modal dialog approach. Updates automatically when selection changes.
"""

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from gilt.gui.services.enrichment_service import EnrichmentData
from gilt.model.account import TransactionGroup
from gilt.services.receipt_ingestion_service import ReceiptData
from gilt.transfer import (
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_META_KEY,
    TRANSFER_METHOD,
    TRANSFER_ROLE,
)


class TransactionDetailPanel(QScrollArea):
    """Scrollable side panel that shows details for the selected transaction."""

    receipt_match_requested = Signal()
    apply_receipt_requested = Signal(object, str)  # ReceiptData, transaction_id
    apply_prediction_requested = Signal(object, str)  # TransactionGroup, predicted category

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
        metadata: dict | None = None,
        receipt_candidates: list[ReceiptData] | None = None,
    ):
        """Update the panel to show details for the given transaction."""
        self._clear()

        if transaction is None:
            self._show_placeholder()
            return

        txn = transaction.primary

        self._layout.addWidget(self._build_basics_section(txn))

        # Show predicted category with apply button if available
        if metadata and metadata.get("predicted_category") and not txn.category:
            self._layout.addWidget(self._build_prediction_section(transaction, metadata))

        if enrichment:
            self._layout.addWidget(self._build_enrichment_section(enrichment, txn.currency))
        else:
            self._layout.addWidget(
                self._build_receipt_candidates_section(txn.transaction_id, receipt_candidates)
            )

        if txn.metadata and TRANSFER_META_KEY in txn.metadata:
            self._layout.addWidget(self._build_transfer_section(txn.metadata[TRANSFER_META_KEY]))

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
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapAllRows)
        form.addRow("Transaction ID:", self._label(txn.transaction_id))
        form.addRow("Date:", self._label(str(txn.date)))
        form.addRow("Account:", self._label(txn.account_id))
        form.addRow("Description:", self._copyable_label(txn.description or ""))
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

    def _build_prediction_section(self, transaction: TransactionGroup, metadata: dict) -> QGroupBox:
        """Build the category prediction group box with apply button."""
        group = QGroupBox("Category Suggestion")
        layout = QVBoxLayout(group)

        predicted = metadata["predicted_category"]
        confidence = metadata.get("confidence", 0.0)

        layout.addWidget(self._label(f"{predicted}"))
        layout.addWidget(self._label(f"Confidence: {confidence:.0%}"))

        apply_btn = QPushButton(f"Apply: {predicted}")
        apply_btn.clicked.connect(
            lambda: self.apply_prediction_requested.emit(transaction, predicted)
        )
        layout.addWidget(apply_btn)

        return group

    def _build_receipt_candidates_section(
        self, transaction_id: str, candidates: list[ReceiptData] | None
    ) -> QGroupBox:
        """Build the receipt matching group box with candidate buttons."""
        group = QGroupBox("Receipt Matching")
        layout = QVBoxLayout(group)

        if candidates is None:
            layout.addWidget(self._label("Loading..."))
            return group

        if not candidates:
            layout.addWidget(self._label("No matching receipts found"))
            return group

        for receipt in candidates:
            desc = receipt.vendor
            if receipt.service:
                desc += f" — {receipt.service}"
            desc += f"\n{receipt.amount} {receipt.currency}"
            if receipt.receipt_date:
                desc += f" ({receipt.receipt_date})"

            btn = QPushButton(f"Apply: {receipt.vendor}")
            btn.setToolTip(desc)
            # Capture receipt in closure
            btn.clicked.connect(
                lambda checked=False, r=receipt: self.apply_receipt_requested.emit(
                    r, transaction_id
                )
            )
            layout.addWidget(self._label(desc))
            layout.addWidget(btn)

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
        if TRANSFER_ROLE in transfer:
            form.addRow("Role:", self._label(transfer[TRANSFER_ROLE]))
        if TRANSFER_COUNTERPARTY_ACCOUNT_ID in transfer:
            form.addRow(
                "Counterparty account:", self._label(transfer[TRANSFER_COUNTERPARTY_ACCOUNT_ID])
            )
        if TRANSFER_METHOD in transfer:
            form.addRow("Method:", self._label(transfer[TRANSFER_METHOD]))
        return group

    def _copyable_label(self, text: str) -> QWidget:
        """Create a label with a copy-to-clipboard button beside it."""
        container = QWidget()
        layout = QHBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)

        label = self._label(text)
        layout.addWidget(label, 1)

        copy_btn = QToolButton()
        copy_btn.setIcon(self.style().standardIcon(QStyle.StandardPixmap.SP_FileIcon))
        copy_btn.setToolTip("Copy to clipboard")
        copy_btn.setIconSize(QSize(14, 14))
        copy_btn.setFixedSize(QSize(20, 20))
        copy_btn.clicked.connect(lambda: QApplication.clipboard().setText(text))
        layout.addWidget(copy_btn, 0, Qt.AlignmentFlag.AlignTop)

        return container

    def _label(self, text: str) -> QLabel:
        """Create a selectable label for form values."""
        label = QLabel(text)
        label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        label.setWordWrap(True)
        return label
