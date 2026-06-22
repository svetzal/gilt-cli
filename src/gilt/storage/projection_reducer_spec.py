"""Specs for gilt.storage.projection_reducer — event application to projection DB."""

from __future__ import annotations

import json
import sqlite3
from decimal import Decimal

from gilt.model.events import (
    DuplicateConfirmed,
    DuplicateRejected,
    TransactionCategorized,
    TransactionDescriptionObserved,
    TransactionEnriched,
    TransactionImported,
)
from gilt.storage.projection_reducer import (
    _apply_description_observed,
    _apply_duplicate_confirmed,
    _apply_duplicate_rejected,
    _apply_transaction_categorized,
    _apply_transaction_enriched,
    _apply_transaction_imported,
    apply_events,
)
from gilt.storage.projection_schema import ensure_projection_schema


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(":memory:")
    ensure_projection_schema(conn)
    return conn


def _make_imported(txn_id: str = "abc1234567890000", **kwargs) -> TransactionImported:
    defaults = dict(
        transaction_date="2024-01-15",
        transaction_id=txn_id,
        source_file="mybank.csv",
        source_account="MYBANK_CHQ",
        raw_description="EXAMPLE UTILITY",
        amount=Decimal("-42.50"),
        currency="CAD",
        raw_data={},
    )
    defaults.update(kwargs)
    return TransactionImported(**defaults)


def _get_row(conn: sqlite3.Connection, txn_id: str) -> dict | None:
    conn.row_factory = sqlite3.Row
    row = conn.execute(
        "SELECT * FROM transaction_projections WHERE transaction_id = ?", (txn_id,)
    ).fetchone()
    return dict(row) if row else None


class DescribeApplyTransactionImported:
    def it_should_insert_a_new_projection_row(self):
        conn = _conn()
        event = _make_imported()
        _apply_transaction_imported(conn, event)
        conn.commit()
        row = _get_row(conn, "abc1234567890000")
        assert row is not None
        assert row["transaction_id"] == "abc1234567890000"
        assert row["canonical_description"] == "EXAMPLE UTILITY"

    def it_should_be_idempotent_on_duplicate_import(self):
        conn = _conn()
        event = _make_imported()
        _apply_transaction_imported(conn, event)
        _apply_transaction_imported(conn, event)
        conn.commit()
        count = conn.execute(
            "SELECT COUNT(*) FROM transaction_projections WHERE transaction_id = ?",
            ("abc1234567890000",),
        ).fetchone()[0]
        assert count == 1

    def it_should_set_description_history_as_json_list(self):
        conn = _conn()
        event = _make_imported()
        _apply_transaction_imported(conn, event)
        conn.commit()
        row = _get_row(conn, "abc1234567890000")
        history = json.loads(row["description_history"])
        assert history == ["EXAMPLE UTILITY"]


class DescribeApplyDescriptionObserved:
    def it_should_update_canonical_description(self):
        conn = _conn()
        _apply_transaction_imported(conn, _make_imported(txn_id="orig000000000000",
                                                          raw_description="OLD DESC"))
        conn.commit()

        event = TransactionDescriptionObserved(
            original_transaction_id="orig000000000000",
            new_transaction_id="new0000000000000",
            transaction_date="2024-01-15",
            original_description="OLD DESC",
            new_description="NEW DESC",
            source_file="mybank.csv",
            source_account="MYBANK_CHQ",
            amount=Decimal("-42.50"),
        )
        _apply_description_observed(conn, event)
        conn.commit()

        row = _get_row(conn, "orig000000000000")
        assert row["canonical_description"] == "NEW DESC"

    def it_should_append_new_description_to_history(self):
        conn = _conn()
        _apply_transaction_imported(conn, _make_imported(txn_id="orig000000000000",
                                                          raw_description="OLD DESC"))
        conn.commit()

        event = TransactionDescriptionObserved(
            original_transaction_id="orig000000000000",
            new_transaction_id="new0000000000000",
            transaction_date="2024-01-15",
            original_description="OLD DESC",
            new_description="NEW DESC",
            source_file="mybank.csv",
            source_account="MYBANK_CHQ",
            amount=Decimal("-42.50"),
        )
        _apply_description_observed(conn, event)
        conn.commit()

        row = _get_row(conn, "orig000000000000")
        history = json.loads(row["description_history"])
        assert "NEW DESC" in history

    def it_should_not_raise_when_original_id_not_found(self):
        conn = _conn()
        event = TransactionDescriptionObserved(
            original_transaction_id="missing000000000",
            new_transaction_id="new0000000000000",
            transaction_date="2024-01-15",
            original_description="OLD",
            new_description="NEW",
            source_file="mybank.csv",
            source_account="MYBANK_CHQ",
            amount=Decimal("-10.00"),
        )
        _apply_description_observed(conn, event)  # should not raise
        conn.commit()


class DescribeApplyTransactionCategorized:
    def it_should_update_category_and_subcategory(self):
        conn = _conn()
        _apply_transaction_imported(conn, _make_imported())
        conn.commit()

        event = TransactionCategorized(
            transaction_id="abc1234567890000",
            category="Bills",
            subcategory="Utilities",
            source="user",
        )
        _apply_transaction_categorized(conn, event)
        conn.commit()

        row = _get_row(conn, "abc1234567890000")
        assert row["category"] == "Bills"
        assert row["subcategory"] == "Utilities"


class DescribeApplyTransactionEnriched:
    def it_should_update_vendor_and_enrichment_fields(self):
        conn = _conn()
        _apply_transaction_imported(conn, _make_imported())
        conn.commit()

        event = TransactionEnriched(
            transaction_id="abc1234567890000",
            vendor="ACME CORP",
            service="Widget Pro",
            invoice_number="INV-001",
            tax_amount=None,
            tax_type=None,
            currency="CAD",
            receipt_file=None,
            enrichment_source="receipt.json",
            source_email=None,
        )
        _apply_transaction_enriched(conn, event)
        conn.commit()

        row = _get_row(conn, "abc1234567890000")
        assert row["vendor"] == "ACME CORP"
        assert row["service"] == "Widget Pro"
        assert row["enrichment_source"] == "receipt.json"


class DescribeApplyDuplicateConfirmed:
    def it_should_mark_duplicate_with_is_duplicate_flag(self):
        conn = _conn()
        _apply_transaction_imported(conn, _make_imported(txn_id="primary00000000"))
        _apply_transaction_imported(conn, _make_imported(txn_id="duplic0000000000"))
        conn.commit()

        event = DuplicateConfirmed(
            suggestion_event_id="evt-suggest-001",
            primary_transaction_id="primary00000000",
            duplicate_transaction_id="duplic0000000000",
            canonical_description="EXAMPLE UTILITY",
            llm_was_correct=True,
        )
        _apply_duplicate_confirmed(conn, event)
        conn.commit()

        dup_row = _get_row(conn, "duplic0000000000")
        assert dup_row["is_duplicate"] == 1
        assert dup_row["primary_transaction_id"] == "primary00000000"


class DescribeApplyDuplicateRejected:
    def it_should_update_last_event_id_for_both_transactions(self):
        conn = _conn()
        _apply_transaction_imported(conn, _make_imported(txn_id="txn1000000000000"))
        _apply_transaction_imported(conn, _make_imported(txn_id="txn2000000000000"))
        conn.commit()

        event = DuplicateRejected(
            suggestion_event_id="evt-suggest-002",
            transaction_id_1="txn1000000000000",
            transaction_id_2="txn2000000000000",
            llm_was_correct=False,
        )
        _apply_duplicate_rejected(conn, event)
        conn.commit()

        row1 = _get_row(conn, "txn1000000000000")
        row2 = _get_row(conn, "txn2000000000000")
        assert row1["last_event_id"] == event.event_id
        assert row2["last_event_id"] == event.event_id


class DescribeApplyEvents:
    def it_should_apply_events_and_update_sequence(self):
        conn = _conn()
        events = [_make_imported(txn_id="abc1234567890000")]
        processed = apply_events(conn, events, start_sequence=0)
        assert processed == 1
        seq = conn.execute(
            "SELECT value FROM projection_metadata WHERE key = 'last_sequence'"
        ).fetchone()
        assert seq is not None
        assert int(seq[0]) == 1

    def it_should_not_update_sequence_when_no_events(self):
        conn = _conn()
        apply_events(conn, [], start_sequence=0)
        seq = conn.execute(
            "SELECT value FROM projection_metadata WHERE key = 'last_sequence'"
        ).fetchone()
        assert seq is None
