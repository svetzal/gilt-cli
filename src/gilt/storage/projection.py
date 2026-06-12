"""
Transaction projection builder for event sourcing.

This module rebuilds the current state of transactions from the immutable
event log. Projections are materialized views that can be rebuilt at any
time by replaying events.

Key Features:
- Rebuild projections from scratch or incrementally
- Track description evolution via TransactionDescriptionObserved events
- Store canonical description (most recent) and complete history
- Derive current state for queries without scanning event log

Privacy: All processing is local-only. No network I/O.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from gilt.model.events import (
    DuplicateConfirmed,
    DuplicateRejected,
    Event,
    TransactionCategorized,
    TransactionDescriptionObserved,
    TransactionEnriched,
    TransactionImported,
)
from gilt.storage.event_store import EventStore


@dataclass
class CategoryHistoryRow:
    """Aggregated categorization history for a description pattern."""

    category: str | None
    subcategory: str | None
    count: int
    total: float
    min_amount: float
    max_amount: float
    latest_date: str


@dataclass
class DuplicateGroupState:
    """Snapshot of duplicate/non-duplicate rows loaded from the projection DB."""

    dup_rows: list[tuple[str, str | None]]
    non_dup_ids: set[str]


@dataclass(frozen=True)
class DuplicateCorrection:
    """A single repair action for a duplicate group.

    kind values:
    - "repoint": set primary_transaction_id = primary_id for txn_id (stale chain repair)
    - "elect_primary": clear is_duplicate flag and primary pointer for txn_id (orphan election)
    - "demote": set is_duplicate=1 and primary_transaction_id = primary_id for txn_id
    """

    kind: str
    txn_id: str
    primary_id: str | None = None


def _uf_find(parent: dict[str, str], x: str) -> str:
    """Path-compressing find for union-find."""
    while parent[x] != x:
        parent[x] = parent[parent[x]]
        x = parent[x]
    return x


def _uf_union(parent: dict[str, str], a: str, b: str) -> None:
    """Union two sets in union-find."""
    ra, rb = _uf_find(parent, a), _uf_find(parent, b)
    if ra != rb:
        parent[ra] = rb


def plan_duplicate_corrections(state: DuplicateGroupState) -> list[DuplicateCorrection]:
    """Pure: compute which duplicate-group repairs are needed given current projection state.

    Identifies two problem patterns and returns correction records for each:
    1. Orphan cycles — components where no member has is_duplicate=0.
       Elects min(members) as primary and demotes the rest.
    2. Stale chains — duplicates whose primary_transaction_id itself has is_duplicate=1.
       Repoints them to the canonical lexicographically-smallest non-dup root.

    Issues no SQL. Callers translate the returned list into UPDATE statements.
    """
    dup_rows = state.dup_rows
    non_dup_ids = state.non_dup_ids

    if not dup_rows:
        return []

    all_ids: set[str] = non_dup_ids | {r[0] for r in dup_rows}
    parent: dict[str, str] = {txn_id: txn_id for txn_id in all_ids}

    for txn_id, primary_id in dup_rows:
        if primary_id and primary_id in all_ids and primary_id != txn_id:
            _uf_union(parent, txn_id, primary_id)

    components: dict[str, list[str]] = {}
    for txn_id in all_ids:
        root = _uf_find(parent, txn_id)
        components.setdefault(root, []).append(txn_id)

    corrections: list[DuplicateCorrection] = []
    for members in components.values():
        non_dup_members = [m for m in members if m in non_dup_ids]
        dup_members = [m for m in members if m not in non_dup_ids]

        if not dup_members:
            continue

        if non_dup_members:
            root = min(non_dup_members)
            for dup_id in dup_members:
                corrections.append(DuplicateCorrection(kind="repoint", txn_id=dup_id, primary_id=root))
        else:
            elected = min(members)
            corrections.append(DuplicateCorrection(kind="elect_primary", txn_id=elected))
            for dup_id in members:
                if dup_id != elected:
                    corrections.append(
                        DuplicateCorrection(kind="demote", txn_id=dup_id, primary_id=elected)
                    )

    return corrections


def find_root_primary(
    lookup: Callable[[str], tuple[bool, str | None] | None],
    txn_id: str,
    max_hops: int = 8,
) -> tuple[str | None, list[str]]:
    """Walk the primary_transaction_id chain to find the root non-duplicate ancestor.

    Pure: takes a `lookup` callable instead of a DB connection, making it
    testable without a live database.

    Args:
        lookup: Given a txn_id, returns (is_duplicate, primary_id) or None if not found.
        txn_id: Starting transaction ID.
        max_hops: Maximum chain length before giving up (cycle guard).

    Returns:
        (root_id, visited): root_id is the first ancestor with is_duplicate=False,
        or None if a cycle/dead-end/max-hops is hit.
    """
    visited: list[str] = []
    current = txn_id
    for _ in range(max_hops):
        if current in visited:
            return None, visited  # cycle detected
        visited.append(current)
        row = lookup(current)
        if row is None:
            return None, visited  # row not found
        is_dup, primary_id = row
        if not is_dup:
            return current, visited  # found a non-duplicate root
        if not primary_id:
            return None, visited  # is_duplicate=True but no pointer — dead end
        current = primary_id
    return None, visited  # exceeded max_hops


def _resolve_root_primary(
    conn: sqlite3.Connection, txn_id: str, max_hops: int = 8
) -> tuple[str | None, list[str]]:
    """Thin wrapper: resolves root via DB query, delegating logic to find_root_primary."""

    def _lookup(t_id: str) -> tuple[bool, str | None] | None:
        cursor = conn.execute(
            "SELECT is_duplicate, primary_transaction_id FROM transaction_projections "
            "WHERE transaction_id = ?",
            (t_id,),
        )
        row = cursor.fetchone()
        if not row:
            return None
        return bool(row[0]), row[1]

    return find_root_primary(_lookup, txn_id, max_hops)


def _normalize_duplicate_groups(conn: sqlite3.Connection) -> None:
    """Thin shell: load duplicate state, compute corrections, apply UPDATEs.

    All decision logic lives in plan_duplicate_corrections.
    """
    cursor = conn.execute(
        "SELECT transaction_id, primary_transaction_id FROM transaction_projections "
        "WHERE is_duplicate = 1"
    )
    dup_rows = cursor.fetchall()

    cursor = conn.execute(
        "SELECT transaction_id FROM transaction_projections WHERE is_duplicate = 0"
    )
    non_dup_ids: set[str] = {row[0] for row in cursor.fetchall()}

    state = DuplicateGroupState(dup_rows=dup_rows, non_dup_ids=non_dup_ids)
    corrections = plan_duplicate_corrections(state)

    for c in corrections:
        if c.kind == "repoint":
            conn.execute(
                "UPDATE transaction_projections "
                "SET primary_transaction_id = ? "
                "WHERE transaction_id = ? AND primary_transaction_id != ?",
                (c.primary_id, c.txn_id, c.primary_id),
            )
        elif c.kind == "elect_primary":
            conn.execute(
                "UPDATE transaction_projections "
                "SET is_duplicate = 0, primary_transaction_id = NULL "
                "WHERE transaction_id = ?",
                (c.txn_id,),
            )
        elif c.kind == "demote":
            conn.execute(
                "UPDATE transaction_projections "
                "SET is_duplicate = 1, primary_transaction_id = ? "
                "WHERE transaction_id = ?",
                (c.primary_id, c.txn_id),
            )


class ProjectionBuilder:
    """Builds transaction projections from event stream."""

    def __init__(self, db_path: Path):
        """Initialize projection builder with database path.

        Args:
            db_path: Path to SQLite database for projections
        """
        self.db_path = db_path
        self._ensure_schema()

    def _ensure_schema(self) -> None:
        """Create projection tables if they don't exist."""
        conn = sqlite3.connect(self.db_path)
        try:
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

            # Migrate existing databases: add enrichment columns if missing
            self._migrate_enrichment_columns(conn)

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
        finally:
            conn.close()

    def _migrate_enrichment_columns(self, conn: sqlite3.Connection) -> None:
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

    def build_from_scratch(self, event_store: EventStore) -> int:
        """Build all projections from event store.

        Deletes existing projections and replays all events to reconstruct
        current state. This is safe because events are immutable.

        Args:
            event_store: Event store to replay events from

        Returns:
            Number of events processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Clear existing projections
            conn.execute("DELETE FROM transaction_projections")
            conn.execute("DELETE FROM projection_metadata")
            conn.commit()

            # Replay all events
            events = event_store.get_all_events()
            processed = self._apply_events(conn, events, start_sequence=0)
            _normalize_duplicate_groups(conn)
            conn.commit()
            return processed
        finally:
            conn.close()

    def build_incremental(self, event_store: EventStore) -> int:
        """Apply only new events since last build.

        More efficient than full rebuild for large event stores.

        Args:
            event_store: Event store to read new events from

        Returns:
            Number of new events processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            # Get last processed sequence number
            cursor = conn.execute(
                "SELECT value FROM projection_metadata WHERE key = 'last_sequence'"
            )
            row = cursor.fetchone()
            last_sequence = int(row[0]) if row else 0

            # Get new events only
            events = event_store.get_events_since(last_sequence)
            if not events:
                return 0

            processed = self._apply_events(conn, events, start_sequence=last_sequence)
            _normalize_duplicate_groups(conn)
            conn.commit()
            return processed
        finally:
            conn.close()

    def _apply_events(
        self, conn: sqlite3.Connection, events: list[Event], start_sequence: int
    ) -> int:
        """Apply a list of events to projections.

        Args:
            conn: Database connection
            events: Events to apply
            start_sequence: Starting sequence number for metadata update

        Returns:
            Number of events processed
        """
        processed = 0

        for event in events:
            if isinstance(event, TransactionImported):
                self._apply_transaction_imported(conn, event)
            elif isinstance(event, TransactionDescriptionObserved):
                self._apply_description_observed(conn, event)
            elif isinstance(event, TransactionCategorized):
                self._apply_transaction_categorized(conn, event)
            elif isinstance(event, TransactionEnriched):
                self._apply_transaction_enriched(conn, event)
            elif isinstance(event, DuplicateConfirmed):
                self._apply_duplicate_confirmed(conn, event)
            elif isinstance(event, DuplicateRejected):
                self._apply_duplicate_rejected(conn, event)

            processed += 1

        # Update last processed sequence
        if events:
            last_event_seq = start_sequence + processed
            conn.execute(
                """
                INSERT OR REPLACE INTO projection_metadata (key, value)
                VALUES ('last_sequence', ?)
                """,
                (str(last_event_seq),),
            )

        conn.commit()
        return processed

    def _apply_transaction_imported(
        self, conn: sqlite3.Connection, event: TransactionImported
    ) -> None:
        """Apply TransactionImported event to projection."""
        # Check if transaction already exists (idempotent)
        cursor = conn.execute(
            "SELECT transaction_id FROM transaction_projections WHERE transaction_id = ?",
            (event.transaction_id,),
        )
        if cursor.fetchone():
            return  # Already imported

        # Create new projection
        description_history = json.dumps([event.raw_description])

        conn.execute(
            """
            INSERT INTO transaction_projections (
                transaction_id, transaction_date, canonical_description,
                description_history, amount, currency, account_id,
                source_file, last_event_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                event.transaction_id,
                event.transaction_date,
                event.raw_description,
                description_history,
                float(event.amount),
                event.currency,
                event.source_account,
                event.source_file,
                event.event_id,
            ),
        )

    def _link_duplicate_if_present(
        self, conn: sqlite3.Connection, event: TransactionDescriptionObserved
    ) -> None:
        # If new transaction_id exists as separate projection, mark it as duplicate.
        # This handles the case where it was imported before we detected the change.
        original_id = event.original_transaction_id
        new_id = event.new_transaction_id

        # Self-reference guard
        if original_id == new_id:
            return

        cursor = conn.execute(
            "SELECT transaction_id FROM transaction_projections WHERE transaction_id = ?",
            (new_id,),
        )
        if cursor.fetchone():
            # Resolve the original to its root in case it is itself a duplicate
            root_id, _ = _resolve_root_primary(conn, original_id)
            actual_primary = root_id if root_id else original_id

            conn.execute(
                """
                UPDATE transaction_projections
                SET is_duplicate = 1,
                    primary_transaction_id = ?,
                    last_event_id = ?
                WHERE transaction_id = ?
                """,
                (
                    actual_primary,
                    event.event_id,
                    new_id,
                ),
            )

    def _apply_description_observed(
        self, conn: sqlite3.Connection, event: TransactionDescriptionObserved
    ) -> None:
        """Apply TransactionDescriptionObserved event to projection.

        When a description changes, we:
        1. Update the canonical description to the new one
        2. Add the new description to the history
        3. Link the new transaction_id to the original (treat as same transaction)
        """
        # Get original transaction
        cursor = conn.execute(
            """
            SELECT canonical_description, description_history
            FROM transaction_projections
            WHERE transaction_id = ?
            """,
            (event.original_transaction_id,),
        )
        row = cursor.fetchone()

        if not row:
            # Original transaction not in projection yet, skip
            return

        canonical_desc, history_json = row
        history = json.loads(history_json) if history_json else []

        # Add new description to history if not already present
        if event.new_description not in history:
            history.append(event.new_description)

        # Update original transaction with new canonical description
        conn.execute(
            """
            UPDATE transaction_projections
            SET canonical_description = ?,
                description_history = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                event.new_description,
                json.dumps(history),
                event.event_id,
                event.original_transaction_id,
            ),
        )

        self._link_duplicate_if_present(conn, event)

    def _apply_transaction_categorized(
        self, conn: sqlite3.Connection, event: TransactionCategorized
    ) -> None:
        """Apply TransactionCategorized event to projection."""
        conn.execute(
            """
            UPDATE transaction_projections
            SET category = ?,
                subcategory = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                event.category,
                event.subcategory,
                event.event_id,
                event.transaction_id,
            ),
        )

    def _apply_transaction_enriched(
        self, conn: sqlite3.Connection, event: TransactionEnriched
    ) -> None:
        """Apply TransactionEnriched event to projection.

        Updates the transaction with vendor/receipt data. If multiple
        enrichments exist for one transaction, the latest wins.
        """
        conn.execute(
            """
            UPDATE transaction_projections
            SET vendor = ?,
                service = ?,
                invoice_number = ?,
                tax_amount = ?,
                tax_type = ?,
                enrichment_currency = ?,
                receipt_file = ?,
                enrichment_source = ?,
                source_email = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                event.vendor,
                event.service,
                event.invoice_number,
                float(event.tax_amount) if event.tax_amount is not None else None,
                event.tax_type,
                event.currency,
                event.receipt_file,
                event.enrichment_source,
                event.source_email,
                event.event_id,
                event.transaction_id,
            ),
        )

    def _apply_duplicate_confirmed(
        self, conn: sqlite3.Connection, event: DuplicateConfirmed
    ) -> None:
        """Apply DuplicateConfirmed event to projection.

        Marks the duplicate transaction with is_duplicate flag and links it
        to the primary transaction. Updates the primary transaction's canonical
        description to the user's preferred choice.

        Guards against:
        - Self-referential events (primary == duplicate)
        - Cycles where the proposed primary is itself a duplicate
        - Direct flips where T1→T2 and then T2→T1 are both confirmed
        """
        primary_id = event.primary_transaction_id
        duplicate_id = event.duplicate_transaction_id

        # Self-reference guard
        if primary_id == duplicate_id:
            return

        # If the proposed primary is itself marked as a duplicate, resolve its root
        cursor = conn.execute(
            "SELECT is_duplicate, primary_transaction_id FROM transaction_projections "
            "WHERE transaction_id = ?",
            (primary_id,),
        )
        primary_row = cursor.fetchone()
        if primary_row and primary_row[0]:  # primary is itself a duplicate
            root_id, _ = _resolve_root_primary(conn, primary_id)
            if root_id:
                primary_id = root_id

        # Direct-flip guard: if the proposed primary currently points at the proposed duplicate,
        # clear that stale marker before writing the new relationship.
        cursor = conn.execute(
            "SELECT primary_transaction_id FROM transaction_projections WHERE transaction_id = ?",
            (primary_id,),
        )
        primary_ptr_row = cursor.fetchone()
        if primary_ptr_row and primary_ptr_row[0] == duplicate_id:
            conn.execute(
                """
                UPDATE transaction_projections
                SET is_duplicate = 0,
                    primary_transaction_id = NULL
                WHERE transaction_id = ?
                """,
                (primary_id,),
            )

        # Update primary transaction with canonical description
        conn.execute(
            """
            UPDATE transaction_projections
            SET canonical_description = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                event.canonical_description,
                event.event_id,
                primary_id,
            ),
        )

        # Mark duplicate transaction
        conn.execute(
            """
            UPDATE transaction_projections
            SET is_duplicate = 1,
                primary_transaction_id = ?,
                last_event_id = ?
            WHERE transaction_id = ?
            """,
            (
                primary_id,
                event.event_id,
                duplicate_id,
            ),
        )

    def _apply_duplicate_rejected(self, conn: sqlite3.Connection, event: DuplicateRejected) -> None:
        """Apply DuplicateRejected event to projection.

        Records the rejection for potential ML training but doesn't change
        projection state. Both transactions remain separate and active.
        """
        # Update last_event_id to track that we processed this feedback
        conn.execute(
            """
            UPDATE transaction_projections
            SET last_event_id = ?
            WHERE transaction_id IN (?, ?)
            """,
            (
                event.event_id,
                event.transaction_id_1,
                event.transaction_id_2,
            ),
        )

    def get_transaction(self, transaction_id: str) -> dict | None:
        """Retrieve a single transaction projection.

        Args:
            transaction_id: Transaction ID to retrieve

        Returns:
            Transaction data as dict, or None if not found
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute(
                "SELECT * FROM transaction_projections WHERE transaction_id = ?", (transaction_id,)
            )
            row = cursor.fetchone()
            return dict(row) if row else None
        finally:
            conn.close()

    def get_all_transactions(self, include_duplicates: bool = False) -> list[dict]:
        """Retrieve all transaction projections.

        Args:
            include_duplicates: Whether to include transactions marked as duplicates

        Returns:
            List of transaction data as dicts
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            if include_duplicates:
                cursor = conn.execute(
                    "SELECT * FROM transaction_projections ORDER BY transaction_date, account_id"
                )
            else:
                cursor = conn.execute(
                    """
                    SELECT * FROM transaction_projections
                    WHERE is_duplicate = 0
                    ORDER BY transaction_date, account_id
                    """
                )
            return [dict(row) for row in cursor.fetchall()]
        finally:
            conn.close()

    def get_current_sequence(self) -> int:
        """Get the last event sequence number that was processed.

        Returns:
            Last processed sequence number, or 0 if no events have been processed
        """
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT value FROM projection_metadata WHERE key = 'last_sequence'"
            )
            row = cursor.fetchone()
            return int(row[0]) if row else 0
        finally:
            conn.close()

    def delete_account_projections(self, account_id: str) -> int:
        """Delete all projection rows for a given account.

        Used during reingest to purge stale projections before replaying events.

        Args:
            account_id: The account whose projections should be removed.

        Returns:
            Number of rows deleted.
        """
        if not self.db_path.exists():
            return 0
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "DELETE FROM transaction_projections WHERE account_id = ?",
                (account_id,),
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()

    def reset_metadata(self) -> None:
        """Clear projection metadata so the next incremental rebuild replays all events.

        Used during reingest to force a full re-projection after purging account data.
        """
        if not self.db_path.exists():
            return
        conn = sqlite3.connect(self.db_path)
        try:
            conn.execute("DELETE FROM projection_metadata")
            conn.commit()
        finally:
            conn.close()

    def get_distinct_account_ids(self) -> list[str]:
        """Return sorted list of non-duplicate account IDs from the projections database."""
        conn = sqlite3.connect(self.db_path)
        try:
            cursor = conn.execute(
                "SELECT DISTINCT account_id FROM transaction_projections "
                "WHERE is_duplicate = 0 ORDER BY account_id"
            )
            return [row[0] for row in cursor.fetchall()]
        finally:
            conn.close()

    def find_category_history(
        self,
        pattern: str,
        *,
        account_id: str | None = None,
        include_uncategorized: bool = False,
        limit: int = 10,
        date_from: str | None = None,
        date_to: str | None = None,
    ) -> list[CategoryHistoryRow]:
        """Aggregate categorization history for transactions matching a description pattern.

        Performs a case-insensitive LIKE match on canonical_description, groups by
        category/subcategory, and returns rows ordered by count descending.

        Args:
            pattern: Substring to search for (wrapped in % wildcards).
            account_id: If set, restrict to transactions for this account.
            include_uncategorized: If True, include transactions with no category.
            limit: Maximum number of result rows to return.
            date_from: ISO date string (YYYY-MM-DD) for lower bound (inclusive).
            date_to: ISO date string (YYYY-MM-DD) for upper bound (inclusive).

        Returns:
            List of CategoryHistoryRow ordered by count descending.
        """
        conn = sqlite3.connect(self.db_path)
        try:
            sql_parts = [
                "SELECT category, subcategory,",
                "       COUNT(*) AS cnt,",
                "       SUM(amount) AS total,",
                "       MIN(amount) AS min_amt,",
                "       MAX(amount) AS max_amt,",
                "       MAX(transaction_date) AS latest",
                "FROM transaction_projections",
                "WHERE is_duplicate = 0",
                "  AND canonical_description LIKE ? COLLATE NOCASE",
            ]
            params: list = [f"%{pattern}%"]

            if account_id is not None:
                sql_parts.append("  AND account_id = ?")
                params.append(account_id)

            if not include_uncategorized:
                sql_parts.append("  AND category IS NOT NULL")

            if date_from is not None:
                sql_parts.append("  AND transaction_date >= ?")
                params.append(date_from)

            if date_to is not None:
                sql_parts.append("  AND transaction_date <= ?")
                params.append(date_to)

            sql_parts.append("GROUP BY category, subcategory")
            sql_parts.append("ORDER BY cnt DESC")

            sql_parts.append("LIMIT ?")
            params.append(limit)

            sql = "\n".join(sql_parts)
            cursor = conn.execute(sql, params)
            rows = cursor.fetchall()
            return [
                CategoryHistoryRow(
                    category=row[0],
                    subcategory=row[1],
                    count=row[2],
                    total=row[3],
                    min_amount=row[4],
                    max_amount=row[5],
                    latest_date=row[6],
                )
                for row in rows
            ]
        finally:
            conn.close()


__all__ = [
    "CategoryHistoryRow",
    "DuplicateCorrection",
    "DuplicateGroupState",
    "ProjectionBuilder",
    "find_root_primary",
    "plan_duplicate_corrections",
]
