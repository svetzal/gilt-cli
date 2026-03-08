"""Tests for receipt match dialog data structures and logic (no Qt required)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path

from gilt.services.receipt_ingestion_service import MatchResult, ReceiptData


def _make_receipt(
    *,
    vendor: str = "Acme Corp",
    service: str | None = "Widget Pro",
    amount: Decimal = Decimal("35.01"),
    invoice_number: str | None = "INV001",
    receipt_date: date = date(2025, 6, 15),
) -> ReceiptData:
    return ReceiptData(
        vendor=vendor,
        service=service,
        amount=amount,
        currency="CAD",
        tax_amount=Decimal("4.03"),
        tax_type="HST",
        receipt_date=receipt_date,
        invoice_number=invoice_number,
        source_email="billing@acme.example",
        receipt_file="Acme-INV001.pdf",
        source_path=Path("/tmp/fake-receipt.json"),
    )


def _make_candidate(
    *,
    transaction_id: str = "abcd1234abcd1234",
    transaction_date: str = "2025-06-15",
    amount: str = "-39.04",
    canonical_description: str = "ACME CORP PURCHASE",
    account_id: str = "MYBANK_CC",
) -> dict:
    return {
        "transaction_id": transaction_id,
        "transaction_date": transaction_date,
        "amount": amount,
        "canonical_description": canonical_description,
        "account_id": account_id,
        "currency": "CAD",
    }


class DescribeMatchResultCategories:
    """Tests for the MatchResult data model used by both dialogs."""

    def it_should_classify_single_candidate_as_matched(self):
        result = MatchResult(
            receipt=_make_receipt(),
            status="matched",
            transaction_id="abcd1234abcd1234",
            candidate_count=1,
            candidates=[_make_candidate()],
            match_confidence="exact",
        )
        assert result.status == "matched"
        assert result.transaction_id == "abcd1234abcd1234"

    def it_should_classify_multiple_candidates_as_ambiguous(self):
        result = MatchResult(
            receipt=_make_receipt(),
            status="ambiguous",
            candidate_count=2,
            candidates=[
                _make_candidate(transaction_id="aaaa111111111111"),
                _make_candidate(transaction_id="bbbb222222222222"),
            ],
        )
        assert result.status == "ambiguous"
        assert result.candidate_count == 2

    def it_should_classify_no_candidates_as_unmatched(self):
        result = MatchResult(
            receipt=_make_receipt(),
            status="unmatched",
            candidate_count=0,
        )
        assert result.status == "unmatched"
        assert result.candidate_count == 0


class DescribeUserSelectedResolution:
    """Tests for creating user-selected MatchResults (as the batch dialog does)."""

    def it_should_create_resolved_match_from_ambiguous(self):
        ambiguous = MatchResult(
            receipt=_make_receipt(),
            status="ambiguous",
            candidate_count=2,
            candidates=[
                _make_candidate(transaction_id="aaaa111111111111"),
                _make_candidate(transaction_id="bbbb222222222222"),
            ],
        )

        # Simulate user selecting the second candidate
        selected = ambiguous.candidates[1]
        resolved = MatchResult(
            receipt=ambiguous.receipt,
            status="matched",
            transaction_id=selected["transaction_id"],
            candidate_count=ambiguous.candidate_count,
            current_description=selected.get("canonical_description", ""),
            candidates=ambiguous.candidates,
            match_confidence="user-selected",
        )

        assert resolved.status == "matched"
        assert resolved.transaction_id == "bbbb222222222222"
        assert resolved.match_confidence == "user-selected"

    def it_should_preserve_receipt_data_through_resolution(self):
        receipt = _make_receipt(vendor="Example Vendor", service="Pro Plan")
        ambiguous = MatchResult(
            receipt=receipt,
            status="ambiguous",
            candidate_count=1,
            candidates=[_make_candidate()],
        )

        resolved = MatchResult(
            receipt=ambiguous.receipt,
            status="matched",
            transaction_id="abcd1234abcd1234",
            match_confidence="user-selected",
        )

        assert resolved.receipt.vendor == "Example Vendor"
        assert resolved.receipt.service == "Pro Plan"
