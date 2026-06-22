"""Specs for gilt.storage.duplicate_normalization — pure duplicate group repair logic."""

from __future__ import annotations

import sqlite3

from gilt.storage.duplicate_normalization import (
    DuplicateGroupState,
    build_duplicate_corrections,
    find_root_primary,
    normalize_duplicate_groups,
)
from gilt.storage.projection_schema import ensure_projection_schema


def _seed_db(conn: sqlite3.Connection) -> None:
    """Create schema in an in-memory connection."""
    ensure_projection_schema(conn)


def _insert_txn(conn: sqlite3.Connection, txn_id: str, is_duplicate: int = 0,
                primary_id: str | None = None) -> None:
    conn.execute(
        """INSERT INTO transaction_projections
           (transaction_id, transaction_date, canonical_description,
            description_history, amount, currency, account_id,
            is_duplicate, primary_transaction_id, last_event_id)
           VALUES (?, '2024-01-15', 'EXAMPLE UTILITY', '[]', -10.0, 'CAD',
                   'MYBANK_CHQ', ?, ?, 'evt-001')
        """,
        (txn_id, is_duplicate, primary_id),
    )
    conn.commit()


class DescribeBuildDuplicateCorrections:
    def it_should_return_empty_list_for_no_duplicates(self):
        state = DuplicateGroupState(dup_rows=[], non_dup_ids={"abc", "def"})
        result = build_duplicate_corrections(state)
        assert result == []

    def it_should_repoint_stale_chain_to_non_dup_root(self):
        # dup_b points to dup_a; dup_a should be repointed to non-dup "primary"
        state = DuplicateGroupState(
            dup_rows=[("dup_a", "non_primary"), ("dup_b", "dup_a")],
            non_dup_ids={"non_primary"},
        )
        result = build_duplicate_corrections(state)
        kinds = {c.kind for c in result}
        assert "repoint" in kinds
        for c in result:
            if c.kind == "repoint":
                assert c.primary_id == "non_primary"

    def it_should_elect_primary_for_orphan_cycle(self):
        # Two dups pointing at each other; no non-dup in group
        state = DuplicateGroupState(
            dup_rows=[("dup_a", "dup_b"), ("dup_b", "dup_a")],
            non_dup_ids=set(),
        )
        result = build_duplicate_corrections(state)
        kinds = [c.kind for c in result]
        assert "elect_primary" in kinds
        assert "demote" in kinds
        # The elected primary should be the lexicographically smallest member
        elected = next(c for c in result if c.kind == "elect_primary")
        assert elected.txn_id == "dup_a"

    def it_should_not_produce_corrections_when_no_dup_members(self):
        # Group with only non-dups: no corrections needed
        state = DuplicateGroupState(
            dup_rows=[],
            non_dup_ids={"txn_a", "txn_b"},
        )
        result = build_duplicate_corrections(state)
        assert result == []


class DescribeFindRootPrimary:
    def it_should_return_non_duplicate_root_directly(self):
        def lookup(t):
            return (False, None) if t == "primary" else None

        root, visited = find_root_primary(lookup, "primary")
        assert root == "primary"

    def it_should_walk_chain_to_non_dup_root(self):
        db = {
            "dup_1": (True, "primary"),
            "primary": (False, None),
        }

        def lookup(t):
            return db.get(t)

        root, visited = find_root_primary(lookup, "dup_1")
        assert root == "primary"
        assert "dup_1" in visited

    def it_should_return_none_on_cycle(self):
        db = {
            "dup_a": (True, "dup_b"),
            "dup_b": (True, "dup_a"),
        }

        def lookup(t):
            return db.get(t)

        root, visited = find_root_primary(lookup, "dup_a")
        assert root is None

    def it_should_return_none_when_row_not_found(self):
        def lookup(t):
            return None

        root, visited = find_root_primary(lookup, "missing")
        assert root is None

    def it_should_return_none_when_max_hops_exceeded(self):
        db = {f"dup_{i}": (True, f"dup_{i + 1}") for i in range(20)}
        db["dup_20"] = (False, None)

        def lookup(t):
            return db.get(t)

        root, visited = find_root_primary(lookup, "dup_0", max_hops=5)
        assert root is None

    def it_should_return_none_for_dead_end_with_no_pointer(self):
        db = {"orphan": (True, None)}

        def lookup(t):
            return db.get(t)

        root, visited = find_root_primary(lookup, "orphan")
        assert root is None


class DescribeNormalizeDuplicateGroups:
    def it_should_repoint_stale_chains_in_database(self):
        conn = sqlite3.connect(":memory:")
        _seed_db(conn)

        _insert_txn(conn, "primary_txn", is_duplicate=0)
        _insert_txn(conn, "dup_a", is_duplicate=1, primary_id="primary_txn")
        # dup_b stale-points to dup_a instead of primary_txn
        _insert_txn(conn, "dup_b", is_duplicate=1, primary_id="dup_a")

        normalize_duplicate_groups(conn)

        row = conn.execute(
            "SELECT primary_transaction_id FROM transaction_projections WHERE transaction_id = 'dup_b'"
        ).fetchone()
        assert row[0] == "primary_txn"

    def it_should_be_idempotent(self):
        conn = sqlite3.connect(":memory:")
        _seed_db(conn)

        _insert_txn(conn, "primary_txn", is_duplicate=0)
        _insert_txn(conn, "dup_a", is_duplicate=1, primary_id="primary_txn")

        normalize_duplicate_groups(conn)
        normalize_duplicate_groups(conn)

        row = conn.execute(
            "SELECT primary_transaction_id FROM transaction_projections WHERE transaction_id = 'dup_a'"
        ).fetchone()
        assert row[0] == "primary_txn"
