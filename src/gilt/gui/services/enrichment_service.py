from __future__ import annotations

"""
Enrichment Service - Loads receipt enrichment data from the event store.

Indexes TransactionEnriched events by transaction_id and provides
display-ready descriptions and detail data for the GUI.
"""

from dataclasses import dataclass
from decimal import Decimal
from typing import Optional

from gilt.model.events import TransactionEnriched


@dataclass
class EnrichmentData:
    """Receipt enrichment data for a single transaction."""

    vendor: str
    service: Optional[str] = None
    invoice_number: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    tax_type: Optional[str] = None
    currency: str = "CAD"
    receipt_file: Optional[str] = None
    enrichment_source: str = ""
    source_email: Optional[str] = None
    match_confidence: Optional[str] = None


class EnrichmentService:
    """Indexes TransactionEnriched events for GUI display."""

    def __init__(self, enrichment_events: list[TransactionEnriched]):
        self._index: dict[str, EnrichmentData] = {}
        for event in enrichment_events:
            self._index[event.transaction_id] = EnrichmentData(
                vendor=event.vendor,
                service=event.service,
                invoice_number=event.invoice_number,
                tax_amount=event.tax_amount,
                tax_type=event.tax_type,
                currency=event.currency,
                receipt_file=event.receipt_file,
                enrichment_source=event.enrichment_source,
                source_email=event.source_email,
                match_confidence=event.match_confidence,
            )

    def get_enrichment(self, transaction_id: str) -> Optional[EnrichmentData]:
        """Get enrichment data for a transaction, or None if not enriched."""
        return self._index.get(transaction_id)

    def get_display_description(self, transaction_id: str) -> Optional[str]:
        """Get enriched display description, or None if not enriched."""
        data = self._index.get(transaction_id)
        if data is None:
            return None
        if data.service:
            return f"{data.vendor} — {data.service}"
        return data.vendor

    def is_enriched(self, transaction_id: str) -> bool:
        """Check if a transaction has enrichment data."""
        return transaction_id in self._index
