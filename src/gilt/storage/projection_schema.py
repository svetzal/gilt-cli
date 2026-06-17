"""
Schema creation and migration for the transaction projection database.
"""

from __future__ import annotations

import sqlite3


def ensure_projection_schema(conn: sqlite3.Connection) -> None:
    """Create projection tables and indexes if they don't exist."""
    conn.execute("""
        CREATE TABLE IF NOT EXISTS transaction_projections (
            transaction_id TEXT PRIMARY KEY,
            transaction_date TEXT NOT NULL,
            canonical_description TEXT NOT NULL,
            description_history TEXT,  -- JSON array of all observed descriptions
            amount REAL NOT NULL,
            currency TEXT NOT NULL,
            account_id TEXT NOT NULL,
            category TEXT,
            subcategory TEXT,
            counterparty TEXT,
            notes TEXT,
            source_file TEXT,
            is_duplicate INTEGER DEFAULT 0,
            primary_transaction_id TEXT,
            last_event_id TEXT,
            projection_version INTEGER DEFAULT 1,
            vendor TEXT,
            service TEXT,
            invoice_number TEXT,
            tax_amount REAL,
            tax_type TEXT,
            enrichment_currency TEXT,
            receipt_file TEXT,
            enrichment_source TEXT,
            source_email TEXT,
            FOREIGN KEY (primary_transaction_id)
                REFERENCES transaction_projections(transaction_id)
        )
    """)

    _migrate_enrichment_columns(conn)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_txn_proj_date
        ON transaction_projections(transaction_date)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_txn_proj_account
        ON transaction_projections(account_id)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_txn_proj_category
        ON transaction_projections(category, subcategory)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS projection_metadata (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL
        )
    """)

    conn.commit()


def _migrate_enrichment_columns(conn: sqlite3.Connection) -> None:
    """Add enrichment columns to existing databases that lack them."""
    cursor = conn.execute("PRAGMA table_info(transaction_projections)")
    existing_columns = {row[1] for row in cursor.fetchall()}

    enrichment_columns = [
        ("vendor", "TEXT"),
        ("service", "TEXT"),
        ("invoice_number", "TEXT"),
        ("tax_amount", "REAL"),
        ("tax_type", "TEXT"),
        ("enrichment_currency", "TEXT"),
        ("receipt_file", "TEXT"),
        ("enrichment_source", "TEXT"),
        ("source_email", "TEXT"),
    ]

    for col_name, col_type in enrichment_columns:
        if col_name not in existing_columns:
            conn.execute(
                f"ALTER TABLE transaction_projections ADD COLUMN {col_name} {col_type}"
            )

    conn.commit()
