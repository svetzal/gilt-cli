from __future__ import annotations

from decimal import Decimal

from gilt.gui.services.enrichment_service import EnrichmentData
from gilt.model.account import TransactionGroup
from gilt.testing import make_group


def _make_group(**kwargs) -> TransactionGroup:
    defaults = dict(
        transaction_id="abc12345deadbeef",
        date="2025-03-15",
        description="SAMPLE STORE ANYTOWN",
        amount=-42.50,
        currency="CAD",
        account_id="MYBANK_CHQ",
    )
    defaults.update(kwargs)
    return make_group(**defaults)


class DescribeTransactionDetailDialog:
    """Tests for data structures feeding the detail dialog (no Qt required)."""

    def it_should_create_enrichment_data_with_all_fields(self):
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
        assert enrichment.service == "Widget Pro"
        assert enrichment.tax_amount == Decimal("5.53")

    def it_should_create_enrichment_data_with_minimal_fields(self):
        enrichment = EnrichmentData(vendor="ACME CORP", enrichment_source="test.json")
        assert enrichment.vendor == "ACME CORP"
        assert enrichment.service is None
        assert enrichment.receipt_file is None

    def it_should_create_transaction_group_with_transfer_metadata(self):
        group = _make_group(
            metadata={
                "transfer": {
                    "role": "source",
                    "counterparty_account_id": "BANK2_CHQ",
                    "method": "EFT",
                }
            }
        )
        assert group.primary.metadata["transfer"]["role"] == "source"
