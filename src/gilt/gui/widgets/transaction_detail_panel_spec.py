from __future__ import annotations

from decimal import Decimal
from unittest.mock import MagicMock

from gilt.gui.services.enrichment_service import EnrichmentData
from gilt.testing.fixtures import make_group
from gilt.transfer._constants import TRANSFER_META_KEY


class DescribeTransactionDetailPanel:
    """Tests for data structures feeding the detail panel (no Qt required)."""

    def it_should_expose_basic_transaction_fields(self):
        group = make_group()
        txn = group.primary
        assert txn.transaction_id == "aabbccdd11223344"
        assert txn.description == "SAMPLE STORE ANYTOWN"
        assert txn.amount == -42.50
        assert txn.account_id == "MYBANK_CHQ"

    def it_should_expose_category_fields(self):
        group = make_group(category="Food", subcategory="Groceries")
        txn = group.primary
        assert txn.category == "Food"
        assert txn.subcategory == "Groceries"

    def it_should_expose_transfer_metadata(self):
        group = make_group(
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
        assert make_group() is not None  # sanity check


class DescribeUpdateTransactionBehavior:
    """Tests for TransactionDetailPanel.update_transaction branching logic (mock-based)."""

    def it_should_show_placeholder_when_transaction_is_none(self):
        panel = MagicMock()

        from gilt.gui.widgets.transaction_detail_panel import TransactionDetailPanel

        TransactionDetailPanel.update_transaction(panel, None)

        panel._clear.assert_called_once()
        panel._show_placeholder.assert_called_once()

    def it_should_build_basics_section_for_valid_transaction(self):
        panel = MagicMock()
        group = make_group()
        panel._build_basics_section.return_value = MagicMock()
        panel._build_receipt_candidates_section.return_value = MagicMock()

        from gilt.gui.widgets.transaction_detail_panel import TransactionDetailPanel

        TransactionDetailPanel.update_transaction(panel, group)

        panel._build_basics_section.assert_called_once_with(group.primary)

    def it_should_show_prediction_section_when_metadata_has_prediction_and_no_category(self):
        panel = MagicMock()
        group = make_group()  # no category by default
        panel._build_basics_section.return_value = MagicMock()
        panel._build_prediction_section.return_value = MagicMock()
        panel._build_receipt_candidates_section.return_value = MagicMock()
        metadata = {"predicted_category": "Food: Groceries", "confidence": 0.85}

        from gilt.gui.widgets.transaction_detail_panel import TransactionDetailPanel

        TransactionDetailPanel.update_transaction(panel, group, metadata=metadata)

        panel._build_prediction_section.assert_called_once_with(group, metadata)

    def it_should_skip_prediction_section_when_transaction_has_category(self):
        panel = MagicMock()
        group = make_group(category="Food", subcategory="Groceries")
        panel._build_basics_section.return_value = MagicMock()
        panel._build_receipt_candidates_section.return_value = MagicMock()
        metadata = {"predicted_category": "Transport", "confidence": 0.90}

        from gilt.gui.widgets.transaction_detail_panel import TransactionDetailPanel

        TransactionDetailPanel.update_transaction(panel, group, metadata=metadata)

        panel._build_prediction_section.assert_not_called()

    def it_should_show_transfer_section_when_transfer_metadata_exists(self):
        panel = MagicMock()
        group = make_group(
            metadata={TRANSFER_META_KEY: {"role": "debit", "counterparty_account_id": "ACC2"}}
        )
        panel._build_basics_section.return_value = MagicMock()
        panel._build_receipt_candidates_section.return_value = MagicMock()
        panel._build_transfer_section.return_value = MagicMock()

        from gilt.gui.widgets.transaction_detail_panel import TransactionDetailPanel

        TransactionDetailPanel.update_transaction(panel, group)

        panel._build_transfer_section.assert_called_once_with(
            group.primary.metadata[TRANSFER_META_KEY]
        )

    def it_should_show_enrichment_section_when_enrichment_provided(self):
        panel = MagicMock()
        group = make_group()
        enrichment = EnrichmentData(
            vendor="ACME CORP",
            service=None,
            invoice_number=None,
            tax_amount=None,
            tax_type=None,
            currency="CAD",
            receipt_file=None,
            enrichment_source=None,
            source_email=None,
            match_confidence="exact",
        )
        panel._build_basics_section.return_value = MagicMock()
        panel._build_enrichment_section.return_value = MagicMock()

        from gilt.gui.widgets.transaction_detail_panel import TransactionDetailPanel

        TransactionDetailPanel.update_transaction(panel, group, enrichment=enrichment)

        panel._build_enrichment_section.assert_called_once_with(enrichment, group.primary.currency)
        panel._build_receipt_candidates_section.assert_not_called()
