"""Specs for gilt.storage.projection_schema — schema creation and migration."""

from __future__ import annotations

import sqlite3

from gilt.storage.projection_schema import _migrate_enrichment_columns, ensure_projection_schema


def _table_columns(conn: sqlite3.Connection, table: str) -> set[str]:
    rows = conn.execute(f"PRAGMA table_info({table})").fetchall()
    return {row[1] for row in rows}


def _index_names(conn: sqlite3.Connection) -> set[str]:
    rows = conn.execute("SELECT name FROM sqlite_master WHERE type='index'").fetchall()
    return {row[0] for row in rows}


class DescribeEnsureProjectionSchema:
    def it_should_create_transaction_projections_table(self):
        conn = sqlite3.connect(":memory:")
        ensure_projection_schema(conn)
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "transaction_projections" in tables

    def it_should_create_projection_metadata_table(self):
        conn = sqlite3.connect(":memory:")
        ensure_projection_schema(conn)
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "projection_metadata" in tables

    def it_should_create_required_indexes(self):
        conn = sqlite3.connect(":memory:")
        ensure_projection_schema(conn)
        names = _index_names(conn)
        assert "idx_txn_proj_date" in names
        assert "idx_txn_proj_account" in names
        assert "idx_txn_proj_category" in names

    def it_should_be_idempotent_on_second_call(self):
        conn = sqlite3.connect(":memory:")
        ensure_projection_schema(conn)
        ensure_projection_schema(conn)  # should not raise
        tables = {
            r[0]
            for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
        }
        assert "transaction_projections" in tables

    def it_should_include_core_columns(self):
        conn = sqlite3.connect(":memory:")
        ensure_projection_schema(conn)
        cols = _table_columns(conn, "transaction_projections")
        for required in [
            "transaction_id",
            "transaction_date",
            "canonical_description",
            "amount",
            "currency",
            "account_id",
            "is_duplicate",
            "primary_transaction_id",
            "last_event_id",
        ]:
            assert required in cols, f"Missing column: {required}"

    def it_should_include_enrichment_columns(self):
        conn = sqlite3.connect(":memory:")
        ensure_projection_schema(conn)
        cols = _table_columns(conn, "transaction_projections")
        for enrichment_col in [
            "vendor",
            "service",
            "invoice_number",
            "tax_amount",
            "tax_type",
            "enrichment_currency",
            "receipt_file",
            "enrichment_source",
            "source_email",
        ]:
            assert enrichment_col in cols, f"Missing enrichment column: {enrichment_col}"


class DescribeMigrateEnrichmentColumns:
    def it_should_add_enrichment_columns_when_absent(self):
        conn = sqlite3.connect(":memory:")
        conn.execute("""
            CREATE TABLE transaction_projections (
                transaction_id TEXT PRIMARY KEY,
                transaction_date TEXT NOT NULL,
                canonical_description TEXT NOT NULL,
                amount REAL NOT NULL,
                currency TEXT NOT NULL,
                account_id TEXT NOT NULL
            )
        """)
        conn.commit()

        _migrate_enrichment_columns(conn)

        cols = _table_columns(conn, "transaction_projections")
        assert "vendor" in cols
        assert "source_email" in cols
        assert "tax_amount" in cols

    def it_should_be_no_op_when_columns_already_present(self):
        conn = sqlite3.connect(":memory:")
        ensure_projection_schema(conn)
        # Running again should not raise
        _migrate_enrichment_columns(conn)
        cols = _table_columns(conn, "transaction_projections")
        assert "vendor" in cols
