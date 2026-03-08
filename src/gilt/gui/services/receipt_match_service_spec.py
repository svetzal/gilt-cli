"""Tests for receipt match service."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.gui.services.receipt_match_service import (
    BatchMatchResult,
    ReceiptMatchService,
    _transaction_group_to_dict,
)
from gilt.model.account import Transaction, TransactionGroup
from gilt.storage.event_store import EventStore


def _make_transaction_group(
    *,
    transaction_id: str = "abcd1234abcd1234",
    txn_date: str = "2025-06-15",
    amount: str = "-39.04",
    account_id: str = "MYBANK_CC",
    description: str = "ACME CORP PURCHASE",
    currency: str = "CAD",
) -> TransactionGroup:
    txn = Transaction(
        transaction_id=transaction_id,
        date=date.fromisoformat(txn_date),
        description=description,
        amount=Decimal(amount),
        currency=currency,
        account_id=account_id,
    )
    return TransactionGroup(group_id=txn.transaction_id, primary=txn)


def _write_receipt_json(path: Path, overrides: dict | None = None) -> Path:
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
        "receipt_file": "Acme-INV001.pdf",
    }
    if overrides:
        data.update(overrides)
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


class DescribeTransactionGroupToDict:
    def it_should_convert_group_to_projection_dict(self):
        group = _make_transaction_group()
        result = _transaction_group_to_dict(group)

        assert result["transaction_id"] == "abcd1234abcd1234"
        assert result["transaction_date"] == "2025-06-15"
        assert result["canonical_description"] == "ACME CORP PURCHASE"
        assert result["amount"] == "-39.04"
        assert result["account_id"] == "MYBANK_CC"
        assert result["currency"] == "CAD"


class DescribeReceiptMatchServiceCandidates:
    def it_should_find_candidates_for_matching_transaction(self):
        with TemporaryDirectory() as tmpdir:
            receipts_dir = Path(tmpdir) / "receipts"
            receipts_dir.mkdir()
            _write_receipt_json(receipts_dir / "acme.json")

            db_path = Path(tmpdir) / "events.db"
            store = EventStore(str(db_path))

            svc = ReceiptMatchService(receipts_dir, store)
            candidates = svc.find_candidates_for_transaction(
                txn_id="abcd1234abcd1234",
                txn_amount=Decimal("-39.04"),
                txn_date=date(2025, 6, 15),
                txn_description="ACME CORP PURCHASE",
                txn_account_id="MYBANK_CC",
            )

            assert len(candidates) == 1
            assert candidates[0].vendor == "Acme Corp"

    def it_should_return_empty_when_no_receipts_match(self):
        with TemporaryDirectory() as tmpdir:
            receipts_dir = Path(tmpdir) / "receipts"
            receipts_dir.mkdir()
            _write_receipt_json(
                receipts_dir / "acme.json",
                overrides={"amount": 999.99},
            )

            db_path = Path(tmpdir) / "events.db"
            store = EventStore(str(db_path))

            svc = ReceiptMatchService(receipts_dir, store)
            candidates = svc.find_candidates_for_transaction(
                txn_id="abcd1234abcd1234",
                txn_amount=Decimal("-39.04"),
                txn_date=date(2025, 6, 15),
            )

            assert candidates == []

    def it_should_return_empty_when_receipts_dir_empty(self):
        with TemporaryDirectory() as tmpdir:
            receipts_dir = Path(tmpdir) / "receipts"
            receipts_dir.mkdir()

            db_path = Path(tmpdir) / "events.db"
            store = EventStore(str(db_path))

            svc = ReceiptMatchService(receipts_dir, store)
            candidates = svc.find_candidates_for_transaction(
                txn_id="abcd1234abcd1234",
                txn_amount=Decimal("-39.04"),
                txn_date=date(2025, 6, 15),
            )

            assert candidates == []


class DescribeReceiptMatchServiceBatch:
    def it_should_categorize_results_as_matched_ambiguous_unmatched(self):
        with TemporaryDirectory() as tmpdir:
            receipts_dir = Path(tmpdir) / "receipts"
            receipts_dir.mkdir()

            # Receipt that matches one transaction
            _write_receipt_json(
                receipts_dir / "match.json",
                overrides={"invoice_number": "INV_MATCH"},
            )

            # Receipt that matches nothing
            _write_receipt_json(
                receipts_dir / "nomatch.json",
                overrides={
                    "amount": 999.99,
                    "invoice_number": "INV_NOMATCH",
                    "date": "2020-01-01",
                },
            )

            db_path = Path(tmpdir) / "events.db"
            store = EventStore(str(db_path))

            svc = ReceiptMatchService(receipts_dir, store)
            transactions = [_make_transaction_group()]

            result = svc.run_batch_matching(transactions)

            assert isinstance(result, BatchMatchResult)
            assert len(result.matched) == 1
            assert len(result.unmatched) == 1

    def it_should_return_empty_when_no_receipt_files_exist(self):
        with TemporaryDirectory() as tmpdir:
            receipts_dir = Path(tmpdir) / "receipts"
            receipts_dir.mkdir()

            db_path = Path(tmpdir) / "events.db"
            store = EventStore(str(db_path))

            svc = ReceiptMatchService(receipts_dir, store)
            result = svc.run_batch_matching([_make_transaction_group()])

            assert result.matched == []
            assert result.ambiguous == []
            assert result.unmatched == []


class DescribeReceiptMatchServiceApplyMatch:
    def it_should_write_transaction_enriched_event(self):
        with TemporaryDirectory() as tmpdir:
            receipts_dir = Path(tmpdir) / "receipts"
            receipts_dir.mkdir()
            _write_receipt_json(receipts_dir / "acme.json")

            db_path = Path(tmpdir) / "events.db"
            store = EventStore(str(db_path))

            svc = ReceiptMatchService(receipts_dir, store)

            # Find candidate and apply
            from gilt.services.receipt_ingestion_service import ReceiptData

            receipt = ReceiptData.from_json_file(receipts_dir / "acme.json")
            svc.apply_match(receipt, "abcd1234abcd1234")

            # Verify event was written
            events = store.get_events_by_type("TransactionEnriched")
            assert len(events) == 1
            assert events[0].transaction_id == "abcd1234abcd1234"
            assert events[0].vendor == "Acme Corp"
            assert events[0].match_confidence == "user-selected"

    def it_should_use_provided_confidence(self):
        with TemporaryDirectory() as tmpdir:
            receipts_dir = Path(tmpdir) / "receipts"
            receipts_dir.mkdir()
            _write_receipt_json(receipts_dir / "acme.json")

            db_path = Path(tmpdir) / "events.db"
            store = EventStore(str(db_path))

            svc = ReceiptMatchService(receipts_dir, store)

            from gilt.services.receipt_ingestion_service import ReceiptData

            receipt = ReceiptData.from_json_file(receipts_dir / "acme.json")
            svc.apply_match(receipt, "abcd1234abcd1234", match_confidence="exact")

            events = store.get_events_by_type("TransactionEnriched")
            assert events[0].match_confidence == "exact"
