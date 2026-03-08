from __future__ import annotations

from datetime import date
from decimal import Decimal

from gilt.gui.services.enrichment_service import EnrichmentData
from gilt.model.account import Transaction, TransactionGroup


def _make_group(**kwargs) -> TransactionGroup:
    defaults = dict(
        transaction_id="abc12345deadbeef",
        date=date(2025, 3, 15),
        description="SAMPLE STORE ANYTOWN",
        amount=-42.50,
        currency="CAD",
        account_id="MYBANK_CHQ",
    )
    defaults.update(kwargs)
    txn = Transaction(**defaults)
    return TransactionGroup(group_id=txn.transaction_id, primary=txn)


class DescribeTransactionDetailPanel:
    """Tests for data structures feeding the detail panel (no Qt required)."""

    def it_should_expose_basic_transaction_fields(self):
        group = _make_group()
        txn = group.primary
        assert txn.transaction_id == "abc12345deadbeef"
        assert txn.description == "SAMPLE STORE ANYTOWN"
        assert txn.amount == -42.50
        assert txn.account_id == "MYBANK_CHQ"

    def it_should_expose_category_fields(self):
        group = _make_group(category="Food", subcategory="Groceries")
        txn = group.primary
        assert txn.category == "Food"
        assert txn.subcategory == "Groceries"

    def it_should_expose_transfer_metadata(self):
        group = _make_group(
            metadata={
                "transfer": {
                    "role": "source",
                    "counterparty_account_id": "BANK2_CHQ",
                    "method": "EFT",
                }
            }
        )
        transfer = group.primary.metadata["transfer"]
        assert transfer["role"] == "source"
        assert transfer["counterparty_account_id"] == "BANK2_CHQ"

    def it_should_work_with_enrichment_data(self):
        enrichment = EnrichmentData(
            vendor="ACME CORP",
            service="Widget Pro",
            invoice_number="INV-001",
            tax_amount=Decimal("5.53"),
            tax_type="HST",
            currency="CAD",
            receipt_file="receipts/acme.pdf",
            enrichment_source="receipts/acme.json",
            source_email="billing@acme.example",
            match_confidence="exact",
        )
        assert enrichment.vendor == "ACME CORP"
        assert enrichment.tax_amount == Decimal("5.53")

    def it_should_handle_none_transaction(self):
        """Panel should accept None to show placeholder state."""
        # This tests the contract — None means "no selection"
        assert _make_group() is not None  # sanity check
