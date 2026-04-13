"""
Receipt Match Service — wraps receipt_ingestion_service logic for GUI use.

Provides candidate lookup, batch matching, and event writing for receipt-to-transaction
matching in the GUI. All processing is local-only.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from gilt.model.events import TransactionEnriched
from gilt.services.receipt_ingestion_service import (
    DEFAULT_VENDOR_PATTERNS,
    BatchMatchResult,
    ReceiptData,
    batch_match_receipts,
    find_already_ingested_invoices,
    match_receipt_to_transactions,
    scan_receipt_files,
)
from gilt.storage.event_store import EventStore


def _transaction_group_to_dict(group) -> dict:
    """Convert a TransactionGroup to the dict format expected by match_receipt_to_transactions."""
    txn = group.primary
    return {
        "transaction_id": txn.transaction_id,
        "transaction_date": str(txn.date),
        "canonical_description": txn.description or "",
        "amount": str(txn.amount),
        "account_id": txn.account_id,
        "currency": txn.currency or "CAD",
    }


class ReceiptMatchService:
    """GUI-oriented service for matching receipts to transactions."""

    def __init__(
        self,
        receipts_dir: Path,
        event_store: EventStore,
    ):
        self.receipts_dir = receipts_dir
        self.event_store = event_store

    def find_candidates_for_transaction(
        self,
        txn_id: str,
        txn_amount: Decimal,
        txn_date: date,
        txn_description: str = "",
        txn_account_id: str = "",
        txn_currency: str = "CAD",
    ) -> list[ReceiptData]:
        """Find receipt candidates that could match a specific transaction.

        Returns a list of ReceiptData objects whose amount and date are
        close enough to be plausible matches.
        """
        json_paths = scan_receipt_files(self.receipts_dir)
        if not json_paths:
            return []

        existing_events = self.event_store.get_events_by_type("TransactionEnriched")
        ingested_invoices = find_already_ingested_invoices(existing_events)

        # Build a single-transaction list for the matching engine
        txn_dict = {
            "transaction_id": txn_id,
            "transaction_date": str(txn_date),
            "canonical_description": txn_description,
            "amount": str(txn_amount),
            "account_id": txn_account_id,
            "currency": txn_currency,
        }

        candidates: list[ReceiptData] = []
        for path in json_paths:
            try:
                receipt = ReceiptData.from_json_file(path)
            except (ValueError, Exception):
                continue
            if receipt.amount is None:
                continue
            if receipt.invoice_number and receipt.invoice_number in ingested_invoices:
                continue

            result = match_receipt_to_transactions(
                receipt,
                [txn_dict],
                vendor_patterns=DEFAULT_VENDOR_PATTERNS,
            )
            if result.status in ("matched", "ambiguous"):
                candidates.append(receipt)

        return candidates

    def run_batch_matching(self, transactions: list) -> BatchMatchResult:
        """Run matching for all provided transactions against all receipts.

        Args:
            transactions: list of TransactionGroup objects.

        Returns:
            BatchMatchResult with categorised results.
        """
        json_paths = scan_receipt_files(self.receipts_dir)
        if not json_paths:
            return BatchMatchResult([], [], [], 0, 0)

        existing_events = self.event_store.get_events_by_type("TransactionEnriched")
        ingested_invoices = find_already_ingested_invoices(existing_events)

        txn_dicts = [_transaction_group_to_dict(g) for g in transactions]

        return batch_match_receipts(
            json_paths,
            txn_dicts,
            ingested_invoices,
            vendor_patterns=DEFAULT_VENDOR_PATTERNS,
        )

    def apply_match(
        self,
        receipt: ReceiptData,
        transaction_id: str,
        match_confidence: str = "user-selected",
    ) -> None:
        """Create and persist a TransactionEnriched event for this match."""
        event = TransactionEnriched(
            transaction_id=transaction_id,
            vendor=receipt.vendor,
            service=receipt.service,
            invoice_number=receipt.invoice_number,
            tax_amount=receipt.tax_amount,
            tax_type=receipt.tax_type,
            currency=receipt.currency,
            receipt_file=receipt.receipt_file,
            enrichment_source=str(receipt.source_path),
            source_email=receipt.source_email,
            match_confidence=match_confidence,
        )
        self.event_store.append_event(event)
