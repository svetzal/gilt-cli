from __future__ import annotations

"""
Summary service — category/subcategory aggregation for the summary command.

Pure functional core: no I/O, no UI imports.
"""

from dataclasses import dataclass

from gilt.model.account import Transaction


@dataclass(frozen=True)
class CategoryRow:
    category: str | None
    count: int
    net: float


@dataclass(frozen=True)
class SubcategoryRow:
    subcategory: str | None
    count: int
    net: float
    pct_of_category: float


def build_category_summary(
    transactions: list[Transaction],
    *,
    include_uncategorized: bool,
) -> list[CategoryRow]:
    """Aggregate transactions by top-level category.

    Args:
        transactions: The transactions to aggregate.
        include_uncategorized: When True, include a row for transactions with
            no category (None or empty string). When False, they are dropped.

    Returns:
        Rows sorted by abs(net) descending, category name ascending as tiebreaker.
    """
    buckets: dict[str | None, list[float]] = {}

    for txn in transactions:
        key: str | None = txn.category if txn.category else None
        if key is None and not include_uncategorized:
            continue
        buckets.setdefault(key, []).append(txn.amount)

    rows: list[CategoryRow] = []
    for category, amounts in buckets.items():
        rows.append(CategoryRow(category=category, count=len(amounts), net=sum(amounts)))

    rows.sort(key=lambda r: (-abs(r.net), r.category or ""))
    return rows


def build_subcategory_summary(
    transactions: list[Transaction],
    category: str,
) -> tuple[float, list[SubcategoryRow]]:
    """Aggregate transactions within one category by subcategory.

    Args:
        transactions: All transactions (will be filtered to the given category).
        category: The category to drill into (case-sensitive).

    Returns:
        A (category_total, rows) tuple. category_total is the signed net for
        the whole category. Rows are sorted by abs(net) descending.
        pct_of_category is 0.0 when category_total == 0.
    """
    matched = [t for t in transactions if t.category == category]

    buckets: dict[str | None, list[float]] = {}
    for txn in matched:
        key: str | None = txn.subcategory if txn.subcategory else None
        buckets.setdefault(key, []).append(txn.amount)

    category_total = sum(amt for amounts in buckets.values() for amt in amounts)

    rows: list[SubcategoryRow] = []
    for subcategory, amounts in buckets.items():
        net = sum(amounts)
        pct = abs(net) / abs(category_total) * 100.0 if category_total != 0.0 else 0.0
        rows.append(
            SubcategoryRow(
                subcategory=subcategory, count=len(amounts), net=net, pct_of_category=pct
            )
        )

    rows.sort(key=lambda r: (-abs(r.net), r.subcategory or ""))
    return category_total, rows


__all__ = [
    "CategoryRow",
    "SubcategoryRow",
    "build_category_summary",
    "build_subcategory_summary",
]
