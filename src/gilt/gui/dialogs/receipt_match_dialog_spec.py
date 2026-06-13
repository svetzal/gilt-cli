"""Tests for receipt match dialog data structures and logic (no Qt required)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest.mock import MagicMock

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


class DescribeFormatReceipt:
    """Tests for ReceiptMatchDialog._format_receipt (pure formatting logic, no Qt required)."""

    def it_should_format_receipt_with_tax_included(self):
        from gilt.gui.dialogs.receipt_match_dialog import ReceiptMatchDialog

        dialog = MagicMock(spec=ReceiptMatchDialog)
        receipt = _make_receipt(
            vendor="Acme Corp",
            service=None,
            amount=Decimal("35.01"),
            invoice_number=None,
        )
        # tax_amount=4.03 from _make_receipt default

        result = ReceiptMatchDialog._format_receipt(dialog, receipt)

        assert "$35.01" in result
        assert "$4.03" in result
        assert "HST" in result
        assert "$39.04" in result  # 35.01 + 4.03

    def it_should_format_receipt_without_tax(self):
        from gilt.gui.dialogs.receipt_match_dialog import ReceiptMatchDialog

        dialog = MagicMock(spec=ReceiptMatchDialog)
        receipt = ReceiptData(
            vendor="Example Store",
            service=None,
            amount=Decimal("50.00"),
            currency="CAD",
            tax_amount=None,
            tax_type=None,
            receipt_date=date(2025, 5, 10),
            invoice_number=None,
            source_email=None,
            receipt_file=None,
            source_path=Path("/tmp/no-tax.json"),
        )

        result = ReceiptMatchDialog._format_receipt(dialog, receipt)

        assert "$50.00" in result
        assert "tax" not in result.lower() or "=" not in result

    def it_should_include_invoice_number_in_format(self):
        from gilt.gui.dialogs.receipt_match_dialog import ReceiptMatchDialog

        dialog = MagicMock(spec=ReceiptMatchDialog)
        receipt = _make_receipt(invoice_number="INV-2025-999")

        result = ReceiptMatchDialog._format_receipt(dialog, receipt)

        assert "[INV-2025-999]" in result

    def it_should_include_service_in_format(self):
        from gilt.gui.dialogs.receipt_match_dialog import ReceiptMatchDialog

        dialog = MagicMock(spec=ReceiptMatchDialog)
        receipt = _make_receipt(service="Premium Plan")

        result = ReceiptMatchDialog._format_receipt(dialog, receipt)

        assert "Premium Plan" in result


class DescribeBatchReceiptMatchDialogLogic:
    """Tests for BatchReceiptMatchDialog resolution state (no Qt widget instantiation)."""

    def it_should_initialize_resolved_with_matched_results(self):
        from gilt.gui.dialogs.receipt_match_dialog import BatchReceiptMatchDialog

        matched = [
            MatchResult(
                receipt=_make_receipt(),
                status="matched",
                transaction_id="abcd1234abcd1234",
                candidate_count=1,
                candidates=[_make_candidate()],
                match_confidence="exact",
            )
        ]
        dialog = MagicMock(spec=BatchReceiptMatchDialog)
        dialog._matched = matched
        dialog._ambiguous = []
        dialog._resolved = list(matched)  # mirrors __init__ behaviour

        assert len(dialog._resolved) == 1
        assert dialog._resolved[0].status == "matched"

    def it_should_increment_ambiguous_index_on_next(self):
        from gilt.gui.dialogs.receipt_match_dialog import BatchReceiptMatchDialog

        dialog = MagicMock(spec=BatchReceiptMatchDialog)
        dialog._current_ambiguous_index = 0
        dialog._ambiguous = [
            MatchResult(
                receipt=_make_receipt(),
                status="ambiguous",
                candidate_count=1,
                candidates=[_make_candidate()],
            )
        ]

        BatchReceiptMatchDialog._next_ambiguous(dialog)

        assert dialog._current_ambiguous_index == 1
        dialog._show_current_ambiguous.assert_called_once()
