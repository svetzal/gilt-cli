"""Specs for gilt.storage.projection_queries — read-model queries."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gilt.storage.projection_queries import (
    CategoryHistoryRow,
    find_category_history,
    get_all_transactions,
    get_current_sequence,
    get_distinct_account_ids,
    get_transaction,
)
from gilt.storage.projection_schema import ensure_projection_schema


def _setup_db(tmp_path: Path) -> Path:
    db_path = tmp_path / "projections.db"
    conn = sqlite3.connect(db_path)
    ensure_projection_schema(conn)
    conn.close()
    return db_path


def _insert_txn(
    db_path: Path,
    txn_id: str,
    date: str = "2024-01-15",
    description: str = "EXAMPLE UTILITY",
    amount: float = -42.50,
    account_id: str = "MYBANK_CHQ",
    is_duplicate: int = 0,
    category: str | None = None,
    subcategory: str | None = None,
) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        """INSERT INTO transaction_projections
           (transaction_id, transaction_date, canonical_description,
            description_history, amount, currency, account_id,
            is_duplicate, last_event_id, category, subcategory)
           VALUES (?, ?, ?, '[]', ?, 'CAD', ?, ?, 'evt-001', ?, ?)
        """,
        (txn_id, date, description, amount, account_id, is_duplicate, category, subcategory),
    )
    conn.commit()
    conn.close()


def _set_sequence(db_path: Path, seq: int) -> None:
    conn = sqlite3.connect(db_path)
    conn.execute(
        "INSERT OR REPLACE INTO projection_metadata (key, value) VALUES ('last_sequence', ?)",
        (str(seq),),
    )
    conn.commit()
    conn.close()


class DescribeGetTransaction:
    def it_should_return_dict_for_existing_transaction(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(db_path, "abc1234567890000")
        result = get_transaction(db_path, "abc1234567890000")
        assert result is not None
        assert result["transaction_id"] == "abc1234567890000"

    def it_should_return_none_for_missing_transaction(self, tmp_path):
        db_path = _setup_db(tmp_path)
        result = get_transaction(db_path, "doesnotexist0000")
        assert result is None


class DescribeGetAllTransactions:
    def it_should_return_non_duplicate_transactions_by_default(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(db_path, "primary00000000", is_duplicate=0)
        _insert_txn(db_path, "duplic0000000000", is_duplicate=1)
        result = get_all_transactions(db_path)
        ids = [r["transaction_id"] for r in result]
        assert "primary00000000" in ids
        assert "duplic0000000000" not in ids

    def it_should_include_duplicates_when_requested(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(db_path, "primary00000000", is_duplicate=0)
        _insert_txn(db_path, "duplic0000000000", is_duplicate=1)
        result = get_all_transactions(db_path, include_duplicates=True)
        ids = [r["transaction_id"] for r in result]
        assert "primary00000000" in ids
        assert "duplic0000000000" in ids

    def it_should_return_empty_list_for_empty_db(self, tmp_path):
        db_path = _setup_db(tmp_path)
        result = get_all_transactions(db_path)
        assert result == []


class DescribeGetCurrentSequence:
    def it_should_return_zero_when_no_metadata_row(self, tmp_path):
        db_path = _setup_db(tmp_path)
        result = get_current_sequence(db_path)
        assert result == 0

    def it_should_return_stored_sequence_value(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _set_sequence(db_path, 42)
        result = get_current_sequence(db_path)
        assert result == 42


class DescribeGetDistinctAccountIds:
    def it_should_return_sorted_account_ids(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(db_path, "txn1", account_id="MYBANK_CHQ", is_duplicate=0)
        _insert_txn(db_path, "txn2", account_id="BANK2_BIZ", is_duplicate=0)
        result = get_distinct_account_ids(db_path)
        assert result == sorted(["MYBANK_CHQ", "BANK2_BIZ"])

    def it_should_exclude_duplicate_transactions(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(db_path, "txn1", account_id="MYBANK_CHQ", is_duplicate=0)
        _insert_txn(db_path, "txn2", account_id="BANK2_BIZ", is_duplicate=1)
        result = get_distinct_account_ids(db_path)
        assert "BANK2_BIZ" not in result
        assert "MYBANK_CHQ" in result

    def it_should_return_each_account_id_once(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(db_path, "txn1", account_id="MYBANK_CHQ", is_duplicate=0)
        _insert_txn(
            db_path,
            "txn2",
            account_id="MYBANK_CHQ",
            is_duplicate=0,
            date="2024-02-01",
            description="SAMPLE STORE",
            amount=-5.00,
        )
        result = get_distinct_account_ids(db_path)
        assert result.count("MYBANK_CHQ") == 1


class DescribeFindCategoryHistory:
    def it_should_return_matching_rows_by_description_pattern(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(
            db_path,
            "txn1",
            description="EXAMPLE UTILITY BILL",
            category="Bills",
            subcategory="Utilities",
            is_duplicate=0,
        )
        _insert_txn(
            db_path,
            "txn2",
            description="SAMPLE STORE",
            category="Shopping",
            subcategory=None,
            is_duplicate=0,
        )
        result = find_category_history(db_path, "EXAMPLE UTILITY")
        descs = [r.category for r in result]
        assert "Bills" in descs
        assert "Shopping" not in descs

    def it_should_filter_by_account_id(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(
            db_path,
            "txn1",
            account_id="MYBANK_CHQ",
            description="ACME CORP",
            category="Bills",
            is_duplicate=0,
        )
        _insert_txn(
            db_path,
            "txn2",
            account_id="BANK2_BIZ",
            description="ACME CORP",
            category="Expense",
            is_duplicate=0,
        )
        result = find_category_history(db_path, "ACME CORP", account_id="MYBANK_CHQ")
        assert all(r.category == "Bills" for r in result)

    def it_should_exclude_uncategorized_by_default(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(db_path, "txn1", description="EXAMPLE UTILITY", category=None, is_duplicate=0)
        result = find_category_history(db_path, "EXAMPLE UTILITY")
        assert result == []

    def it_should_include_uncategorized_when_requested(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(db_path, "txn1", description="EXAMPLE UTILITY", category=None, is_duplicate=0)
        result = find_category_history(db_path, "EXAMPLE UTILITY", include_uncategorized=True)
        assert len(result) >= 1

    def it_should_respect_limit_parameter(self, tmp_path):
        db_path = _setup_db(tmp_path)
        for i in range(5):
            _insert_txn(
                db_path,
                f"txn{i}",
                description="EXAMPLE UTILITY",
                category=f"Cat{i}",
                is_duplicate=0,
                date=f"2024-0{i + 1}-01",
                amount=float(-i - 1),
            )
        result = find_category_history(db_path, "EXAMPLE UTILITY", limit=2)
        assert len(result) <= 2

    def it_should_return_correct_aggregation_fields(self, tmp_path):
        db_path = _setup_db(tmp_path)
        _insert_txn(
            db_path,
            "txn1",
            description="EXAMPLE UTILITY",
            category="Bills",
            amount=-42.50,
            is_duplicate=0,
        )
        _insert_txn(
            db_path,
            "txn2",
            description="EXAMPLE UTILITY",
            category="Bills",
            amount=-10.00,
            is_duplicate=0,
            date="2024-02-01",
        )
        result = find_category_history(db_path, "EXAMPLE UTILITY")
        assert len(result) == 1
        row = result[0]
        assert isinstance(row, CategoryHistoryRow)
        assert row.count == 2
        assert row.category == "Bills"
