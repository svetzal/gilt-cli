from __future__ import annotations

"""
Receipt coverage reporting: compute which transactions have receipts attached.
"""

import contextlib
from dataclasses import dataclass, field
from datetime import date


@dataclass
class CoverageRow:
    """One row in the receipt coverage summary table."""

    category: str
    subcategory: str  # subcategory value when grouping by category; empty when grouping by account
    account_id: str  # account_id value when grouping by account; empty when grouping by category
    total_txns: int
    with_receipt: int
    without_receipt: int
    coverage_pct: int | str  # whole-number % or "—" when total_txns == 0
    net_amount: float


@dataclass
class MissingReceiptRow:
    """A transaction that lacks a receipt attachment."""

    transaction_id: str
    date: str
    description: str
    amount: float
    account_id: str


@dataclass
class ReceiptCoverageResult:
    """Result of receipt coverage analysis."""

    coverage_rows: list[CoverageRow] = field(default_factory=list)
    missing_rows: list[MissingReceiptRow] = field(default_factory=list)


def _is_in_fy(txn_date_str: str, fy_range: tuple[date, date] | None) -> bool:
    """Return True if the date string falls within fy_range (or no range is set)."""
    if fy_range is None:
        return True
    with contextlib.suppress(ValueError):
        txn_date = date.fromisoformat(txn_date_str)
        return fy_range[0] <= txn_date <= fy_range[1]
    return False


def build_receipt_coverage(
    rows: list[dict],
    *,
    category: str = "Mojility",
    group_by_account: bool = False,
    fy_range: tuple[date, date] | None = None,
) -> ReceiptCoverageResult:
    """Build receipt coverage statistics from projection rows.

    Filters to transactions in the given category and optional fiscal-year range,
    then groups by (category, subcategory) or by account_id.

    Args:
        rows: Transaction projection rows (dicts from ProjectionBuilder).
        category: Category to filter on (default "Mojility").
        group_by_account: If True, group by account_id; otherwise by (category, subcategory).
        fy_range: Optional (start, end) inclusive date range.

    Returns:
        ReceiptCoverageResult containing both summary and missing-receipt rows.
    """
    matching = [
        row
        for row in rows
        if row.get("category") == category
        and _is_in_fy(row.get("transaction_date") or "", fy_range)
    ]

    # Accumulate per-group buckets
    buckets: dict[str, dict] = {}
    for row in matching:
        key = row.get("account_id") or "" if group_by_account else f"{row.get('subcategory') or ''}"

        if key not in buckets:
            buckets[key] = {
                "category": row.get("category") or "",
                "subcategory": (row.get("subcategory") or "") if not group_by_account else "",
                "account_id": (row.get("account_id") or "") if group_by_account else "",
                "total_txns": 0,
                "with_receipt": 0,
                "net_amount": 0.0,
            }

        bucket = buckets[key]
        bucket["total_txns"] += 1
        if row.get("receipt_file"):
            bucket["with_receipt"] += 1
        bucket["net_amount"] += float(row.get("amount") or 0.0)

    coverage_rows: list[CoverageRow] = []
    for key in sorted(buckets):
        b = buckets[key]
        total = b["total_txns"]
        with_r = b["with_receipt"]
        without_r = total - with_r
        pct: int | str = round(with_r / total * 100) if total > 0 else "—"
        coverage_rows.append(
            CoverageRow(
                category=b["category"],
                subcategory=b["subcategory"],
                account_id=b["account_id"],
                total_txns=total,
                with_receipt=with_r,
                without_receipt=without_r,
                coverage_pct=pct,
                net_amount=round(b["net_amount"], 2),
            )
        )

    missing_rows: list[MissingReceiptRow] = [
        MissingReceiptRow(
            transaction_id=row.get("transaction_id") or "",
            date=row.get("transaction_date") or "",
            description=row.get("canonical_description") or "",
            amount=float(row.get("amount") or 0.0),
            account_id=row.get("account_id") or "",
        )
        for row in sorted(matching, key=lambda r: r.get("transaction_date") or "")
        if not row.get("receipt_file")
    ]

    return ReceiptCoverageResult(coverage_rows=coverage_rows, missing_rows=missing_rows)


__all__ = [
    "build_receipt_coverage",
    "CoverageRow",
    "MissingReceiptRow",
    "ReceiptCoverageResult",
]
