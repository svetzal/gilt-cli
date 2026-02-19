from __future__ import annotations

"""Tests for receipt ingestion service."""

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.services.receipt_ingestion_service import (
    ReceiptData,
    find_already_ingested_invoices,
    match_receipt_to_transactions,
    scan_receipt_files,
)


def _write_receipt_json(path: Path, overrides: dict | None = None) -> Path:
    """Helper to write a receipt JSON file."""
    data = {
        "schema": "mailctl.receipt.v1",
        "vendor": "Acme Corp",
        "service": "Widget Pro",
        "amount": 35.01,
        "currency": "CAD",
        "tax": {"amount": 4.03, "type": "HST"},
        "date": "2025-06-15",
        "invoice_number": "INV001",
        "source_email": "billing@acme.example",
        "source_account": "example",
        "email_uid": 100,
        "receipt_file": "Acme-INV001.pdf",
    }
    if overrides:
        data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def _make_receipt(
    *,
    vendor: str = "Acme Corp",
    service: str | None = "Widget Pro",
    amount: Decimal = Decimal("35.01"),
    currency: str = "CAD",
    date_str: str = "2025-06-15",
    invoice_number: str | None = "INV001",
) -> ReceiptData:
    """Helper to build a ReceiptData directly (no file I/O)."""
    return ReceiptData(
        vendor=vendor,
        service=service,
        amount=amount,
        currency=currency,
        tax_amount=None,
        tax_type=None,
        receipt_date=date.fromisoformat(date_str),
        invoice_number=invoice_number,
        source_email=None,
        receipt_file=None,
        source_path=Path("/tmp/fake-receipt.json"),
    )


def _make_txn_row(
    *,
    transaction_id: str = "abcd1234abcd1234",
    transaction_date: str = "2025-06-15",
    amount: str = "-35.01",
    account_id: str = "MYBANK_CC",
    canonical_description: str = "ACME CORP PURCHASE",
) -> dict:
    """Helper to build a projection row dict."""
    return {
        "transaction_id": transaction_id,
        "transaction_date": transaction_date,
        "amount": amount,
        "account_id": account_id,
        "canonical_description": canonical_description,
        "currency": "CAD",
    }


class DescribeReceiptDataParsing:
    def it_should_parse_valid_receipt_json(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path)

            receipt = ReceiptData.from_json_file(path)

            assert receipt.vendor == "Acme Corp"
            assert receipt.service == "Widget Pro"
            assert receipt.amount == Decimal("35.01")
            assert receipt.currency == "CAD"
            assert receipt.tax_amount == Decimal("4.03")
            assert receipt.tax_type == "HST"
            assert receipt.receipt_date == date(2025, 6, 15)
            assert receipt.invoice_number == "INV001"
            assert receipt.source_email == "billing@acme.example"
            assert receipt.receipt_file == "Acme-INV001.pdf"
            assert receipt.source_path == path

    def it_should_reject_unsupported_schema(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"schema": "unknown.v2"})

            try:
                ReceiptData.from_json_file(path)
                assert False, "Should have raised ValueError"
            except ValueError as e:
                assert "Unsupported schema" in str(e)

    def it_should_handle_missing_optional_fields(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            data = {
                "schema": "mailctl.receipt.v1",
                "vendor": "Simple Vendor",
                "amount": 10.00,
                "date": "2025-01-01",
            }
            path.write_text(json.dumps(data), encoding="utf-8")

            receipt = ReceiptData.from_json_file(path)

            assert receipt.vendor == "Simple Vendor"
            assert receipt.service is None
            assert receipt.tax_amount is None
            assert receipt.tax_type is None
            assert receipt.invoice_number is None
            assert receipt.source_email is None
            assert receipt.receipt_file is None


class DescribeScanReceiptFiles:
    def it_should_find_json_files_recursively(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            (root / "sub").mkdir()
            _write_receipt_json(root / "a.json")
            _write_receipt_json(root / "sub" / "b.json")
            (root / "ignore.txt").write_text("not json")

            paths = scan_receipt_files(root)

            assert len(paths) == 2
            assert all(p.suffix == ".json" for p in paths)

    def it_should_filter_by_year(self):
        with TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            _write_receipt_json(root / "a.json", overrides={"date": "2025-06-15"})
            _write_receipt_json(root / "b.json", overrides={"date": "2024-06-15"})

            paths = scan_receipt_files(root, year=2025)

            assert len(paths) == 1
            assert paths[0].name == "a.json"

    def it_should_return_empty_for_nonexistent_dir(self):
        paths = scan_receipt_files(Path("/nonexistent/dir"))
        assert paths == []


class DescribeMatchReceiptToTransactions:
    def it_should_match_single_transaction(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path)
            receipt = ReceiptData.from_json_file(path)

            # Bank charges tax-inclusive total: 35.01 + 4.03 HST = 39.04
            transactions = [_make_txn_row(amount="-39.04")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "matched"
            assert result.transaction_id == "abcd1234abcd1234"
            assert result.candidate_count == 1

    def it_should_match_within_amount_tolerance(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"amount": 35.01})
            receipt = ReceiptData.from_json_file(path)

            # Tax-inclusive total is 39.04; 39.05 is within $0.02 tolerance
            transactions = [_make_txn_row(amount="-39.05")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "matched"

    def it_should_not_match_outside_amount_tolerance(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"amount": 35.01})
            receipt = ReceiptData.from_json_file(path)

            # Tax-inclusive total is 39.04; 39.10 is outside $0.02 tolerance
            transactions = [_make_txn_row(amount="-39.10")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "unmatched"

    def it_should_match_within_date_window(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"date": "2025-06-15"})
            receipt = ReceiptData.from_json_file(path)

            # Tax-inclusive total: 35.01 + 4.03 = 39.04
            transactions = [_make_txn_row(amount="-39.04", transaction_date="2025-06-18")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "matched"

    def it_should_not_match_outside_date_window(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"date": "2025-06-15"})
            receipt = ReceiptData.from_json_file(path)

            # Amount matches but date is 10 days away (outside 3-day window)
            transactions = [_make_txn_row(amount="-39.04", transaction_date="2025-06-25")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "unmatched"

    def it_should_report_ambiguous_when_multiple_matches(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path)
            receipt = ReceiptData.from_json_file(path)

            # Tax-inclusive total: 35.01 + 4.03 = 39.04
            transactions = [
                _make_txn_row(transaction_id="aaaa111111111111", amount="-39.04"),
                _make_txn_row(transaction_id="bbbb222222222222", amount="-39.04"),
            ]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "ambiguous"
            assert result.candidate_count == 2

    def it_should_filter_by_account(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path)
            receipt = ReceiptData.from_json_file(path)

            # Tax-inclusive total: 35.01 + 4.03 = 39.04
            transactions = [
                _make_txn_row(
                    transaction_id="aaaa111111111111", account_id="MYBANK_CC", amount="-39.04"
                ),
                _make_txn_row(
                    transaction_id="bbbb222222222222", account_id="BANK2_CHQ", amount="-39.04"
                ),
            ]
            result = match_receipt_to_transactions(
                receipt, transactions, account_id="MYBANK_CC"
            )

            assert result.status == "matched"
            assert result.transaction_id == "aaaa111111111111"


    def it_should_set_confidence_exact_on_match(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path)
            receipt = ReceiptData.from_json_file(path)

            # Tax-inclusive total: 35.01 + 4.03 = 39.04
            transactions = [_make_txn_row(amount="-39.04")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "matched"
            assert result.match_confidence == "exact"


class DescribeFxTolerantMatching:
    def it_should_match_usd_receipt_to_cad_transaction_within_tolerance(self):
        receipt = _make_receipt(amount=Decimal("13.49"), currency="USD", date_str="2025-06-15")
        # Bank posts $13.55 CAD for a $13.49 USD charge (~0.4% diff)
        transactions = [_make_txn_row(amount="-13.55")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "matched"
        assert result.match_confidence == "fx-adjusted"

    def it_should_reject_when_amount_exceeds_eight_percent(self):
        receipt = _make_receipt(amount=Decimal("13.49"), currency="USD", date_str="2025-06-15")
        # 15.00 CAD is ~11% more than 13.49 — too far
        transactions = [_make_txn_row(amount="-15.00")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "unmatched"

    def it_should_not_apply_fx_when_currencies_match(self):
        receipt = _make_receipt(amount=Decimal("13.49"), currency="CAD", date_str="2025-06-15")
        # Same currency, 13.55 is outside exact tolerance ($0.02) but within 8%
        transactions = [_make_txn_row(amount="-13.55")]

        result = match_receipt_to_transactions(receipt, transactions)

        # Should NOT match via FX since currencies are the same
        assert result.status == "unmatched"

    def it_should_use_tighter_date_window_of_two_days(self):
        receipt = _make_receipt(amount=Decimal("13.49"), currency="USD", date_str="2025-06-15")
        # 3 days away — within exact window but outside FX window
        transactions = [_make_txn_row(amount="-13.55", transaction_date="2025-06-18")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "unmatched"

    def it_should_match_within_two_day_fx_window(self):
        receipt = _make_receipt(amount=Decimal("13.49"), currency="USD", date_str="2025-06-15")
        transactions = [_make_txn_row(amount="-13.55", transaction_date="2025-06-17")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "matched"
        assert result.match_confidence == "fx-adjusted"


class DescribeVendorPatternMatching:
    def it_should_match_when_vendor_pattern_found_and_amount_close(self):
        receipt = _make_receipt(
            vendor="Acme Corp", amount=Decimal("35.01"), date_str="2025-06-15"
        )
        transactions = [
            _make_txn_row(amount="-35.50", canonical_description="ACME.COM/BILL ON")
        ]
        vendor_patterns = {"acme corp": ["ACME.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "pattern-assisted"

    def it_should_not_match_when_vendor_pattern_not_in_description(self):
        receipt = _make_receipt(
            vendor="Acme Corp", amount=Decimal("35.01"), date_str="2025-06-15"
        )
        transactions = [
            _make_txn_row(amount="-35.50", canonical_description="SOME OTHER STORE")
        ]
        vendor_patterns = {"acme corp": ["ACME.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "unmatched"

    def it_should_not_match_when_amount_exceeds_eight_percent(self):
        receipt = _make_receipt(
            vendor="Acme Corp", amount=Decimal("35.01"), date_str="2025-06-15"
        )
        transactions = [
            _make_txn_row(amount="-40.00", canonical_description="ACME.COM/BILL ON")
        ]
        vendor_patterns = {"acme corp": ["ACME.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "unmatched"

    def it_should_match_case_insensitively(self):
        receipt = _make_receipt(
            vendor="Acme Corp", amount=Decimal("35.01"), date_str="2025-06-15"
        )
        transactions = [
            _make_txn_row(amount="-35.50", canonical_description="acme.com/bill purchase")
        ]
        vendor_patterns = {"acme corp": ["ACME.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "pattern-assisted"


class DescribeTaxInclusiveMatching:
    def it_should_match_using_total_when_receipt_has_tax(self):
        receipt = ReceiptData(
            vendor="Acme Corp",
            service="Widget Pro",
            amount=Decimal("11.99"),
            currency="CAD",
            tax_amount=Decimal("1.56"),
            tax_type="HST",
            receipt_date=date(2025, 6, 15),
            invoice_number="INV099",
            source_email=None,
            receipt_file=None,
            source_path=Path("/tmp/fake-receipt.json"),
        )
        # Bank charges 13.55 (11.99 + 1.56 HST)
        transactions = [_make_txn_row(amount="-13.55")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "matched"
        assert result.match_confidence == "exact"

    def it_should_not_match_pretax_amount_when_tax_present(self):
        receipt = ReceiptData(
            vendor="Acme Corp",
            service="Widget Pro",
            amount=Decimal("11.99"),
            currency="CAD",
            tax_amount=Decimal("1.56"),
            tax_type="HST",
            receipt_date=date(2025, 6, 15),
            invoice_number="INV099",
            source_email=None,
            receipt_file=None,
            source_path=Path("/tmp/fake-receipt.json"),
        )
        # Transaction matches pre-tax amount only — should NOT match
        transactions = [_make_txn_row(amount="-11.99")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "unmatched"

    def it_should_use_pretax_amount_when_no_tax(self):
        receipt = _make_receipt(amount=Decimal("11.99"))
        transactions = [_make_txn_row(amount="-11.99")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "matched"
        assert result.match_confidence == "exact"

    def it_should_use_tax_total_for_fx_matching(self):
        receipt = ReceiptData(
            vendor="Acme Corp",
            service=None,
            amount=Decimal("11.99"),
            currency="USD",
            tax_amount=Decimal("1.56"),
            tax_type="HST",
            receipt_date=date(2025, 6, 15),
            invoice_number=None,
            source_email=None,
            receipt_file=None,
            source_path=Path("/tmp/fake-receipt.json"),
        )
        # Bank charges 13.80 CAD for a 13.55 USD total (~1.8% FX diff)
        transactions = [_make_txn_row(amount="-13.80")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "matched"
        assert result.match_confidence == "fx-adjusted"

    def it_should_use_tax_total_for_pattern_matching(self):
        receipt = ReceiptData(
            vendor="Acme Corp",
            service=None,
            amount=Decimal("35.01"),
            currency="CAD",
            tax_amount=Decimal("4.03"),
            tax_type="HST",
            receipt_date=date(2025, 6, 15),
            invoice_number=None,
            source_email=None,
            receipt_file=None,
            source_path=Path("/tmp/fake-receipt.json"),
        )
        # Bank charges 39.50 (close to 39.04 total, within 8%)
        transactions = [
            _make_txn_row(amount="-39.50", canonical_description="ACME.COM/BILL ON")
        ]
        vendor_patterns = {"acme corp": ["ACME.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "pattern-assisted"


class DescribeVendorPatternFilteringOnExactAndFx:
    """When vendor_patterns are provided and the receipt vendor has known patterns,
    exact and FX strategies should also verify the description matches."""

    def it_should_reject_exact_match_when_vendor_has_patterns_but_description_differs(self):
        receipt = _make_receipt(
            vendor="Sample Store", amount=Decimal("49.99"), date_str="2025-06-15"
        )
        transactions = [
            _make_txn_row(
                amount="-49.99",
                canonical_description="UNRELATED VENDOR PURCHASE",
            )
        ]
        vendor_patterns = {"sample store": ["SAMPLE.COM/BILL", "SAMPLE STORE"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "unmatched"

    def it_should_accept_exact_match_when_vendor_has_patterns_and_description_matches(self):
        receipt = _make_receipt(
            vendor="Sample Store", amount=Decimal("49.99"), date_str="2025-06-15"
        )
        transactions = [
            _make_txn_row(
                amount="-49.99",
                canonical_description="SAMPLE.COM/BILL SUBSCRIPTION",
            )
        ]
        vendor_patterns = {"sample store": ["SAMPLE.COM/BILL", "SAMPLE STORE"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "exact"

    def it_should_keep_exact_match_when_vendor_has_no_patterns_defined(self):
        receipt = _make_receipt(
            vendor="Unknown Vendor", amount=Decimal("49.99"), date_str="2025-06-15"
        )
        transactions = [
            _make_txn_row(
                amount="-49.99",
                canonical_description="TOTALLY DIFFERENT DESCRIPTION",
            )
        ]
        vendor_patterns = {"sample store": ["SAMPLE.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "exact"

    def it_should_reject_fx_match_when_vendor_has_patterns_but_description_differs(self):
        receipt = _make_receipt(
            vendor="Sample Store",
            amount=Decimal("13.49"),
            currency="USD",
            date_str="2025-06-15",
        )
        transactions = [
            _make_txn_row(
                amount="-13.55",
                canonical_description="UNRELATED VENDOR PURCHASE",
            )
        ]
        vendor_patterns = {"sample store": ["SAMPLE.COM/BILL", "SAMPLE STORE"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "unmatched"

    def it_should_accept_fx_match_when_vendor_has_patterns_and_description_matches(self):
        receipt = _make_receipt(
            vendor="Sample Store",
            amount=Decimal("13.49"),
            currency="USD",
            date_str="2025-06-15",
        )
        transactions = [
            _make_txn_row(
                amount="-13.55",
                canonical_description="SAMPLE.COM/BILL SUBSCRIPTION",
            )
        ]
        vendor_patterns = {"sample store": ["SAMPLE.COM/BILL", "SAMPLE STORE"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "fx-adjusted"

    def it_should_keep_fx_match_when_vendor_has_no_patterns_defined(self):
        receipt = _make_receipt(
            vendor="Unknown Vendor",
            amount=Decimal("13.49"),
            currency="USD",
            date_str="2025-06-15",
        )
        transactions = [
            _make_txn_row(
                amount="-13.55",
                canonical_description="TOTALLY DIFFERENT DESCRIPTION",
            )
        ]
        vendor_patterns = {"sample store": ["SAMPLE.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "fx-adjusted"

    def it_should_prevent_false_positive_cross_vendor_match(self):
        """Reproduces the Apple/$49.99 receipt matching FEELHEALGROW/$50.00 bug."""
        receipt = _make_receipt(
            vendor="Sample Store", amount=Decimal("49.99"), date_str="2025-06-15"
        )
        transactions = [
            _make_txn_row(
                amount="-50.00",
                canonical_description="UNRELATED VENDOR OTHERTOWN",
            )
        ]
        vendor_patterns = {"sample store": ["SAMPLE.COM/BILL", "SAMPLE.COM"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "unmatched"

    def it_should_still_allow_pattern_fallback_when_exact_rejected_by_vendor(self):
        """When exact is rejected due to vendor mismatch, pattern strategy can still match."""
        receipt = _make_receipt(
            vendor="Sample Store", amount=Decimal("49.99"), date_str="2025-06-15"
        )
        transactions = [
            # This one has right amount but wrong description → exact rejected
            _make_txn_row(
                transaction_id="wrong_desc_1234567",
                amount="-49.99",
                canonical_description="UNRELATED VENDOR PURCHASE",
            ),
            # This one has close amount and right description → pattern match
            _make_txn_row(
                transaction_id="right_desc_1234567",
                amount="-50.50",
                canonical_description="SAMPLE.COM/BILL SUBSCRIPTION",
            ),
        ]
        vendor_patterns = {"sample store": ["SAMPLE.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "pattern-assisted"
        assert result.transaction_id == "right_desc_1234567"


class DescribeMatchConfidencePreference:
    def it_should_prefer_exact_over_fx_match(self):
        receipt = _make_receipt(
            amount=Decimal("35.01"), currency="USD", date_str="2025-06-15"
        )
        transactions = [
            # Exact amount match (even though currencies differ)
            _make_txn_row(
                transaction_id="exact_id_12345678",
                amount="-35.01",
            ),
            # FX-close match
            _make_txn_row(
                transaction_id="fx_id_123456789ab",
                amount="-35.80",
            ),
        ]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "matched"
        assert result.match_confidence == "exact"
        assert result.transaction_id == "exact_id_12345678"

    def it_should_prefer_exact_over_pattern_when_description_matches(self):
        receipt = _make_receipt(
            vendor="Acme Corp", amount=Decimal("35.01"), date_str="2025-06-15"
        )
        transactions = [
            # Exact amount match with matching description
            _make_txn_row(
                transaction_id="exact_id_12345678",
                amount="-35.01",
                canonical_description="ACME.COM/BILL ON",
            ),
            # Pattern match but different amount
            _make_txn_row(
                transaction_id="pattern_id_123456",
                amount="-35.80",
                canonical_description="ACME.COM/BILL ON",
            ),
        ]
        vendor_patterns = {"acme corp": ["ACME.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "exact"
        assert result.transaction_id == "exact_id_12345678"

    def it_should_fall_to_pattern_when_exact_rejected_by_vendor_filter(self):
        receipt = _make_receipt(
            vendor="Acme Corp", amount=Decimal("35.01"), date_str="2025-06-15"
        )
        transactions = [
            # Exact amount but wrong description → rejected by vendor filter
            _make_txn_row(
                transaction_id="exact_id_12345678",
                amount="-35.01",
                canonical_description="GENERIC STORE",
            ),
            # Pattern match with right description
            _make_txn_row(
                transaction_id="pattern_id_123456",
                amount="-35.80",
                canonical_description="ACME.COM/BILL ON",
            ),
        ]
        vendor_patterns = {"acme corp": ["ACME.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "pattern-assisted"
        assert result.transaction_id == "pattern_id_123456"

    def it_should_fall_through_to_fx_when_no_exact(self):
        receipt = _make_receipt(
            amount=Decimal("13.49"), currency="USD", date_str="2025-06-15"
        )
        # Only FX-range match, no exact
        transactions = [_make_txn_row(amount="-13.80")]

        result = match_receipt_to_transactions(receipt, transactions)

        assert result.status == "matched"
        assert result.match_confidence == "fx-adjusted"

    def it_should_fall_through_to_pattern_when_no_exact_or_fx(self):
        receipt = _make_receipt(
            vendor="Acme Corp", amount=Decimal("35.01"), date_str="2025-06-15"
        )
        # Amount within 8% but not exact, same currency (no FX)
        transactions = [
            _make_txn_row(amount="-36.00", canonical_description="ACME.COM/BILL ON")
        ]
        vendor_patterns = {"acme corp": ["ACME.COM/BILL"]}

        result = match_receipt_to_transactions(
            receipt, transactions, vendor_patterns=vendor_patterns
        )

        assert result.status == "matched"
        assert result.match_confidence == "pattern-assisted"


class DescribeFindAlreadyIngestedInvoices:
    def it_should_collect_invoice_numbers_from_events(self):
        class FakeEvent:
            def __init__(self, inv):
                self.invoice_number = inv

        events = [FakeEvent("INV001"), FakeEvent("INV002"), FakeEvent(None)]
        result = find_already_ingested_invoices(events)

        assert result == {"INV001", "INV002"}

    def it_should_return_empty_set_for_no_events(self):
        result = find_already_ingested_invoices([])
        assert result == set()
