"""
Duplicate diagnostics service - functional core for diagnosing duplicate projection issues.

Detects three classes of problems in projection rows:
- orphan_group: a connected component where no member has is_duplicate=0
- stale_primary: is_duplicate=1 but primary_transaction_id points at a non-existent or
  itself-duplicate row
- self_referential: is_duplicate=1 and primary_transaction_id == transaction_id

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. All functions accept pre-loaded data (no file I/O).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


@dataclass
class DuplicateIssue:
    """A projection row with a duplicate-state problem."""

    transaction_id: str
    transaction_date: str
    account_id: str
    canonical_description: str
    amount: float
    issue_class: Literal["orphan_group", "stale_primary", "self_referential"]
    primary_pointed_at: str | None


class DuplicateDiagnosticsService:
    """
    Service for diagnosing duplicate-projection issues.

    Accepts a list of projection row dicts (all rows, including duplicates).
    Returns a list of DuplicateIssue objects, one per problematic row.

    Priority order for classification (highest wins):
    1. self_referential
    2. orphan_group
    3. stale_primary
    """

    def find_issues(self, rows: list[dict]) -> list[DuplicateIssue]:
        """Scan projection rows and return all rows with duplicate-state issues.

        Args:
            rows: List of projection row dicts. Each dict must contain at least:
                  transaction_id, transaction_date, account_id, canonical_description,
                  amount, is_duplicate, primary_transaction_id.

        Returns:
            List of DuplicateIssue objects for all rows with problems.
        """
        all_ids: set[str] = {row["transaction_id"] for row in rows}
        id_to_row: dict[str, dict] = {row["transaction_id"]: row for row in rows}

        # Build connected components (union-find) for duplicate groups
        parent: dict[str, str] = {txn_id: txn_id for txn_id in all_ids}

        for row in rows:
            if row["is_duplicate"] and row["primary_transaction_id"]:
                primary = row["primary_transaction_id"]
                # Only union within known rows — excludes self-ref and dangling pointers
                if primary in all_ids and primary != row["transaction_id"]:
                    self._union(parent, row["transaction_id"], primary)

        components: dict[str, list[str]] = {}
        for txn_id in all_ids:
            root = self._find(parent, txn_id)
            components.setdefault(root, []).append(txn_id)

        # Determine which components are orphan groups (no non-duplicate member).
        # A single-member component whose pointer is outside the dataset is stale_primary,
        # not orphan_group. Only classify as orphan_group when the component has multiple
        # known-row members and none of them has is_duplicate=0.
        orphan_component_roots: set[str] = set()
        for root, members in components.items():
            if len(members) < 2:
                # Single-member "component" — could be stale_primary or self_referential.
                # Do not classify as orphan_group here; those checks happen per-row below.
                continue
            has_primary = any(not id_to_row[m]["is_duplicate"] for m in members)
            if not has_primary:
                orphan_component_roots.add(root)

        issues: list[DuplicateIssue] = []

        for row in rows:
            if not row["is_duplicate"]:
                continue
            issue = self._classify_row(row, parent, orphan_component_roots, all_ids, id_to_row)
            if issue is not None:
                issues.append(issue)

        return issues

    def _classify_row(
        self,
        row: dict,
        parent: dict[str, str],
        orphan_component_roots: set[str],
        all_ids: set[str],
        id_to_row: dict[str, dict],
    ) -> DuplicateIssue | None:
        """Classify a single is_duplicate=1 row and return a DuplicateIssue or None."""
        txn_id = row["transaction_id"]
        primary_id = row["primary_transaction_id"]

        # Priority 1: self_referential
        if primary_id == txn_id:
            issue_class: Literal["orphan_group", "stale_primary", "self_referential"] = (
                "self_referential"
            )
        # Priority 2: orphan_group (multi-member cycle with no non-duplicate member)
        elif self._find(parent, txn_id) in orphan_component_roots:
            issue_class = "orphan_group"
        # Priority 3: stale_primary
        elif (
            primary_id is None or primary_id not in all_ids or id_to_row[primary_id]["is_duplicate"]
        ):
            issue_class = "stale_primary"
        else:
            return None

        return DuplicateIssue(
            transaction_id=txn_id,
            transaction_date=row["transaction_date"],
            account_id=row["account_id"],
            canonical_description=row["canonical_description"],
            amount=float(row["amount"]),
            issue_class=issue_class,
            primary_pointed_at=primary_id,
        )

    def _find(self, parent: dict[str, str], x: str) -> str:
        """Path-compressing find for union-find."""
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def _union(self, parent: dict[str, str], a: str, b: str) -> None:
        """Union two sets in union-find."""
        ra, rb = self._find(parent, a), self._find(parent, b)
        if ra != rb:
            parent[ra] = rb


__all__ = ["DuplicateDiagnosticsService", "DuplicateIssue"]
