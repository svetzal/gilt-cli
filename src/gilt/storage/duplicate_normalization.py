"""
Pure duplicate normalization logic for transaction projections.

Module-level functions with no database dependency. All decision logic for
duplicate-group repair lives here; callers translate the returned corrections
into SQL updates.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from dataclasses import dataclass


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


def build_duplicate_corrections(state: DuplicateGroupState) -> list[DuplicateCorrection]:
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
                corrections.append(
                    DuplicateCorrection(kind="repoint", txn_id=dup_id, primary_id=root)
                )
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


def normalize_duplicate_groups(conn: sqlite3.Connection) -> None:
    """Thin shell: load duplicate state, compute corrections, apply UPDATEs.

    All decision logic lives in build_duplicate_corrections.
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
    corrections = build_duplicate_corrections(state)

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
