"""Specs for ingest_receipts_review.py — interactive review for the ingest-receipts command."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch


def _make_receipt(vendor="ACME CORP", amount=Decimal("99.99")):
    from gilt.services.receipt_ingestion_service import ReceiptData

    return ReceiptData(
        vendor=vendor,
        service=None,
        amount=amount,
        currency="CAD",
        tax_amount=None,
        tax_type=None,
        receipt_date=date(2025, 6, 1),
        invoice_number="INV-001",
        source_email=None,
        receipt_file=None,
        source_path=Path("/tmp/receipt.json"),
    )


def _make_ambiguous_match():
    from gilt.services.receipt_ingestion_service import MatchResult

    candidates = [
        {
            "transaction_id": "abcd1234efgh5678",
            "transaction_date": "2025-06-01",
            "amount": "99.99",
            "canonical_description": "ACME CORP PAYMENT",
            "account_id": "MYBANK_CC",
        },
        {
            "transaction_id": "wxyz9876mnop5432",
            "transaction_date": "2025-06-01",
            "amount": "99.99",
            "canonical_description": "ACME CORP SUBSCRIPTION",
            "account_id": "MYBANK_CC",
        },
    ]
    return MatchResult(
        receipt=_make_receipt(),
        status="ambiguous",
        transaction_id=None,
        candidate_count=2,
        candidates=candidates,
    )


class DescribeResolveAmbiguousInteractively:
    def it_should_return_empty_list_when_user_skips(self):
        from gilt.cli.command.ingest_receipts_review import run_ambiguous_interactively

        match = _make_ambiguous_match()
        with patch("gilt.cli.command.ingest_receipts_review.Prompt.ask", return_value="s"):
            result = run_ambiguous_interactively([match])
        assert result == []

    def it_should_return_resolved_match_when_user_selects_candidate(self):
        from gilt.cli.command.ingest_receipts_review import run_ambiguous_interactively

        match = _make_ambiguous_match()
        with patch("gilt.cli.command.ingest_receipts_review.Prompt.ask", return_value="1"):
            result = run_ambiguous_interactively([match])
        assert len(result) == 1
        assert result[0].status == "matched"
        assert result[0].transaction_id == "abcd1234efgh5678"
