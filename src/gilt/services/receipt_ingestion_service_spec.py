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

            transactions = [_make_txn_row()]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "matched"
            assert result.transaction_id == "abcd1234abcd1234"
            assert result.candidate_count == 1

    def it_should_match_within_amount_tolerance(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"amount": 35.01})
            receipt = ReceiptData.from_json_file(path)

            transactions = [_make_txn_row(amount="-35.02")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "matched"

    def it_should_not_match_outside_amount_tolerance(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"amount": 35.01})
            receipt = ReceiptData.from_json_file(path)

            transactions = [_make_txn_row(amount="-35.10")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "unmatched"

    def it_should_match_within_date_window(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"date": "2025-06-15"})
            receipt = ReceiptData.from_json_file(path)

            transactions = [_make_txn_row(transaction_date="2025-06-18")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "matched"

    def it_should_not_match_outside_date_window(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path, overrides={"date": "2025-06-15"})
            receipt = ReceiptData.from_json_file(path)

            transactions = [_make_txn_row(transaction_date="2025-06-25")]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "unmatched"

    def it_should_report_ambiguous_when_multiple_matches(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path)
            receipt = ReceiptData.from_json_file(path)

            transactions = [
                _make_txn_row(transaction_id="aaaa111111111111"),
                _make_txn_row(transaction_id="bbbb222222222222"),
            ]
            result = match_receipt_to_transactions(receipt, transactions)

            assert result.status == "ambiguous"
            assert result.candidate_count == 2

    def it_should_filter_by_account(self):
        with TemporaryDirectory() as tmpdir:
            path = Path(tmpdir) / "receipt.json"
            _write_receipt_json(path)
            receipt = ReceiptData.from_json_file(path)

            transactions = [
                _make_txn_row(transaction_id="aaaa111111111111", account_id="MYBANK_CC"),
                _make_txn_row(transaction_id="bbbb222222222222", account_id="BANK2_CHQ"),
            ]
            result = match_receipt_to_transactions(
                receipt, transactions, account_id="MYBANK_CC"
            )

            assert result.status == "matched"
            assert result.transaction_id == "aaaa111111111111"


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
