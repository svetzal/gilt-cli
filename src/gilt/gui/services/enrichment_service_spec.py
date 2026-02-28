from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from gilt.gui.services.enrichment_service import EnrichmentService
from gilt.model.events import TransactionEnriched


class DescribeEnrichmentService:
    def it_should_return_none_for_unknown_transaction(self):
        service = EnrichmentService([])
        assert service.get_enrichment("unknown_id") is None

    def it_should_index_enrichment_by_transaction_id(self):
        event = TransactionEnriched(
            transaction_id="txn_001",
            vendor="ACME CORP",
            service="Widget Pro",
            enrichment_source="receipts/acme.json",
        )
        service = EnrichmentService([event])

        result = service.get_enrichment("txn_001")
        assert result is not None
        assert result.vendor == "ACME CORP"
        assert result.service == "Widget Pro"

    def it_should_use_latest_enrichment_when_multiple_exist(self):
        event1 = TransactionEnriched(
            transaction_id="txn_001",
            vendor="Old Vendor",
            enrichment_source="receipts/old.json",
            event_timestamp=datetime(2025, 1, 1),
        )
        event2 = TransactionEnriched(
            transaction_id="txn_001",
            vendor="New Vendor",
            service="Premium Plan",
            enrichment_source="receipts/new.json",
            event_timestamp=datetime(2025, 6, 1),
        )
        service = EnrichmentService([event1, event2])

        result = service.get_enrichment("txn_001")
        assert result.vendor == "New Vendor"
        assert result.service == "Premium Plan"

    def it_should_build_display_description_with_vendor_only(self):
        event = TransactionEnriched(
            transaction_id="txn_001",
            vendor="ACME CORP",
            enrichment_source="receipts/acme.json",
        )
        service = EnrichmentService([event])

        assert service.get_display_description("txn_001") == "ACME CORP"

    def it_should_build_display_description_with_vendor_and_service(self):
        event = TransactionEnriched(
            transaction_id="txn_001",
            vendor="ACME CORP",
            service="Widget Pro",
            enrichment_source="receipts/acme.json",
        )
        service = EnrichmentService([event])

        assert service.get_display_description("txn_001") == "ACME CORP — Widget Pro"

    def it_should_return_none_display_for_unknown_transaction(self):
        service = EnrichmentService([])
        assert service.get_display_description("unknown") is None

    def it_should_report_which_transactions_are_enriched(self):
        event = TransactionEnriched(
            transaction_id="txn_001",
            vendor="ACME CORP",
            enrichment_source="receipts/acme.json",
        )
        service = EnrichmentService([event])

        assert service.is_enriched("txn_001") is True
        assert service.is_enriched("txn_002") is False

    def it_should_preserve_all_enrichment_fields(self):
        event = TransactionEnriched(
            transaction_id="txn_001",
            vendor="ACME CORP",
            service="Widget Pro",
            invoice_number="INV-001",
            tax_amount=Decimal("5.25"),
            tax_type="HST",
            currency="USD",
            receipt_file="receipts/acme.pdf",
            enrichment_source="receipts/acme.json",
            source_email="billing@acme.example",
            match_confidence="exact",
        )
        service = EnrichmentService([event])

        result = service.get_enrichment("txn_001")
        assert result.invoice_number == "INV-001"
        assert result.tax_amount == Decimal("5.25")
        assert result.tax_type == "HST"
        assert result.currency == "USD"
        assert result.receipt_file == "receipts/acme.pdf"
        assert result.enrichment_source == "receipts/acme.json"
        assert result.source_email == "billing@acme.example"
        assert result.match_confidence == "exact"
