from __future__ import annotations

"""
Shared section builders for transaction detail views.

Extracted from TransactionDetailDialog and TransactionDetailPanel to eliminate
knowledge duplication in _build_enrichment_section, _build_transfer_section,
and _build_basics_section.
"""

from collections.abc import Callable

from PySide6.QtWidgets import QFormLayout, QGroupBox, QLabel, QWidget

from gilt.gui.services.enrichment_service import EnrichmentData
from gilt.transfer import (
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_METHOD,
    TRANSFER_ROLE,
)


def build_basics_section(
    label_fn: Callable[[str], QLabel],
    txn,
    *,
    form_setup_fn: Callable[[QFormLayout], None] | None = None,
    description_label_fn: Callable[[str], QWidget] | None = None,
) -> QGroupBox:
    """Build the transaction basics group box.

    Args:
        label_fn: Factory for selectable QLabel widgets.
        txn: Transaction (primary) to display.
        form_setup_fn: Optional callback applied to the QFormLayout before rows are added,
            used e.g. to set row wrap policy.
        description_label_fn: Optional factory for the description row value widget.
            Falls back to ``label_fn`` when None.
    """
    group = QGroupBox("Transaction")
    form = QFormLayout(group)
    if form_setup_fn is not None:
        form_setup_fn(form)

    desc_fn = description_label_fn if description_label_fn is not None else label_fn

    form.addRow("Transaction ID:", label_fn(txn.transaction_id))
    form.addRow("Date:", label_fn(str(txn.date)))
    form.addRow("Account:", label_fn(txn.account_id))
    form.addRow("Description:", desc_fn(txn.description or ""))
    form.addRow("Amount:", label_fn(f"{txn.amount:.2f} {txn.currency or 'CAD'}"))
    if txn.category:
        cat_text = txn.category
        if txn.subcategory:
            cat_text += f": {txn.subcategory}"
        form.addRow("Category:", label_fn(cat_text))
    if txn.counterparty:
        form.addRow("Counterparty:", label_fn(txn.counterparty))
    if txn.notes:
        form.addRow("Notes:", label_fn(txn.notes))
    if txn.source_file:
        form.addRow("Source file:", label_fn(txn.source_file))
    return group


def build_enrichment_section(
    label_fn: Callable[[str], QLabel],
    enrichment: EnrichmentData,
    txn_currency: str | None,
) -> QGroupBox:
    """Build the receipt enrichment group box.

    Args:
        label_fn: Factory for selectable QLabel widgets.
        enrichment: Receipt enrichment data to display.
        txn_currency: Currency of the parent transaction for comparison.
    """
    group = QGroupBox("Receipt Enrichment")
    form = QFormLayout(group)
    form.addRow("Vendor:", label_fn(enrichment.vendor))
    if enrichment.service:
        form.addRow("Service:", label_fn(enrichment.service))
    if enrichment.invoice_number:
        form.addRow("Invoice #:", label_fn(enrichment.invoice_number))
    if enrichment.tax_amount is not None:
        tax_text = f"{enrichment.tax_amount}"
        if enrichment.tax_type:
            tax_text += f" ({enrichment.tax_type})"
        form.addRow("Tax:", label_fn(tax_text))
    if enrichment.currency and enrichment.currency != (txn_currency or "CAD"):
        form.addRow("Receipt currency:", label_fn(enrichment.currency))
    if enrichment.receipt_file:
        form.addRow("Receipt PDF:", label_fn(enrichment.receipt_file))
    if enrichment.source_email:
        form.addRow("Source email:", label_fn(enrichment.source_email))
    if enrichment.match_confidence:
        form.addRow("Match confidence:", label_fn(enrichment.match_confidence))
    return group


def build_transfer_section(
    label_fn: Callable[[str], QLabel],
    transfer: dict,
) -> QGroupBox:
    """Build the transfer link group box.

    Args:
        label_fn: Factory for selectable QLabel widgets.
        transfer: Transfer metadata dict from transaction metadata.
    """
    group = QGroupBox("Transfer Link")
    form = QFormLayout(group)
    if TRANSFER_ROLE in transfer:
        form.addRow("Role:", label_fn(transfer[TRANSFER_ROLE]))
    if TRANSFER_COUNTERPARTY_ACCOUNT_ID in transfer:
        form.addRow(
            "Counterparty account:", label_fn(transfer[TRANSFER_COUNTERPARTY_ACCOUNT_ID])
        )
    if TRANSFER_METHOD in transfer:
        form.addRow("Method:", label_fn(transfer[TRANSFER_METHOD]))
    return group
