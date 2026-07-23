from __future__ import annotations

"""
Transaction Query Service - pure filtering and aggregation logic.

Accepts Transaction objects directly; no file I/O, no projections database,
no UI imports (rich, typer, PySide6).
"""

import logging
from dataclasses import dataclass
from datetime import date

from gilt.model.account import Transaction
from gilt.transfer import (
    ROLE_CREDIT,
    ROLE_DEBIT,
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_META_KEY,
    TRANSFER_ROLE,
)

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TransactionFilter:
    """Criteria for filtering a list of Transaction objects.

    All fields are optional; only non-None values are applied.
    Multiple non-None fields are combined with AND semantics.

    Fields:
        account_id: Exact match on transaction account_id.
        account_ids: Match if account_id is any of these values.
        year: Calendar year of transaction date (transaction.date.year == year).
        fy_range: Inclusive date range (start, end); overrides year when both supplied.
        date_start: Inclusive lower bound on transaction date.
        date_end: Inclusive upper bound on transaction date.
        amount_eq: Exact signed amount within 0.01 tolerance.
        amount_min: Signed lower bound (inclusive).
        amount_max: Signed upper bound (inclusive).
        min_abs_amount: Absolute-value lower bound; matches |amount| >= min_abs_amount.
        max_abs_amount: Absolute-value upper bound; matches |amount| <= max_abs_amount.
        category: Case-insensitive category match.
        categories: Case-insensitive match against any of these categories.
        subcategory: Case-insensitive subcategory match.
        uncategorized_only: Match only transactions with a blank category.
        search_text: Case-insensitive substring match against description or counterparty.
    """

    account_id: str | None = None
    account_ids: tuple[str, ...] | None = None
    year: int | None = None
    fy_range: tuple[date, date] | None = None
    date_start: date | None = None
    date_end: date | None = None
    amount_eq: float | None = None
    amount_min: float | None = None
    amount_max: float | None = None
    min_abs_amount: float | None = None
    max_abs_amount: float | None = None
    category: str | None = None
    categories: tuple[str, ...] | None = None
    subcategory: str | None = None
    uncategorized_only: bool = False
    search_text: str | None = None


@dataclass
class TransactionTotals:
    """Aggregated credit, debit, and net amounts for a set of transactions."""

    credits: float
    debits: float
    net: float


def _passes_account_filter(t: Transaction, criteria: TransactionFilter) -> bool:
    if criteria.account_id is not None and t.account_id != criteria.account_id:
        return False
    return not (criteria.account_ids is not None and t.account_id not in criteria.account_ids)


def _passes_date_filter(t: Transaction, criteria: TransactionFilter) -> bool:
    if criteria.fy_range is not None:
        if not (criteria.fy_range[0] <= t.date <= criteria.fy_range[1]):
            return False
    elif criteria.year is not None and t.date.year != criteria.year:
        return False
    if criteria.date_start is not None and t.date < criteria.date_start:
        return False
    return not (criteria.date_end is not None and t.date > criteria.date_end)


def _passes_amount_filter(t: Transaction, criteria: TransactionFilter) -> bool:
    if criteria.amount_eq is not None and abs(t.amount - criteria.amount_eq) > 0.01:
        return False
    if criteria.amount_min is not None and t.amount < criteria.amount_min:
        return False
    if criteria.amount_max is not None and t.amount > criteria.amount_max:
        return False
    if criteria.min_abs_amount is not None and abs(t.amount) < criteria.min_abs_amount:
        return False
    return not (
        criteria.max_abs_amount is not None and abs(t.amount) > criteria.max_abs_amount
    )


def _passes_category_filter(t: Transaction, criteria: TransactionFilter) -> bool:
    if (
        criteria.category is not None
        and (t.category or "").lower() != criteria.category.lower()
    ):
        return False
    if criteria.categories is not None and (t.category or "").lower() not in {
        c.lower() for c in criteria.categories
    }:
        return False
    if (
        criteria.subcategory is not None
        and (t.subcategory or "").lower() != criteria.subcategory.lower()
    ):
        return False
    return not (criteria.uncategorized_only and (t.category or "").strip())


def _passes_text_filter(t: Transaction, criteria: TransactionFilter) -> bool:
    if criteria.search_text is None:
        return True
    needle = criteria.search_text.lower()
    return needle in (t.description or "").lower() or needle in (
        t.counterparty or ""
    ).lower()


class TransactionQueryService:
    """Pure business logic for filtering and querying transactions.

    All methods accept Transaction objects directly and return plain data.
    No I/O, no UI imports.
    """

    def find_matching(
        self,
        transactions: list[Transaction],
        criteria: TransactionFilter,
    ) -> list[Transaction]:
        """Filter transactions by all non-None criteria (AND semantics).

        Each active criterion must be satisfied for a transaction to be included.

        Args:
            transactions: All transactions to filter from.
            criteria: Filter criteria; only non-None fields are applied.

        Returns:
            Subset of transactions matching all active criteria.
        """
        return [
            t
            for t in transactions
            if _passes_account_filter(t, criteria)
            and _passes_date_filter(t, criteria)
            and _passes_amount_filter(t, criteria)
            and _passes_category_filter(t, criteria)
            and _passes_text_filter(t, criteria)
        ]

    def find_transactions(
        self,
        transactions: list[Transaction],
        *,
        account_id: str,
        year: int | None,
        limit: int | None,
    ) -> list[Transaction]:
        """Filter, sort, and optionally limit transactions.

        Filters to the given account_id and optional year, then sorts by
        (date asc, transaction_id asc). Applies limit last.

        Args:
            transactions: All transactions to filter from.
            account_id: Only include transactions for this account.
            year: Only include transactions from this year (None = all years).
            limit: Maximum number to return (None = all).

        Returns:
            Sorted and optionally limited list of matching transactions.
        """
        criteria = TransactionFilter(account_id=account_id, year=year)
        result = self.find_matching(transactions, criteria)
        result.sort(key=lambda t: (t.date, t.transaction_id))
        if limit is not None:
            result = result[:limit]
        return result

    def get_totals(self, transactions: list[Transaction]) -> TransactionTotals:
        """Calculate sum of credits, debits, and net for a list of transactions.

        Credits: positive amounts summed.
        Debits: negative amounts summed (remains negative).
        Net: total of all amounts.

        Returns:
            TransactionTotals with credits, debits, and net.
        """
        credits = 0.0
        debits = 0.0
        net = 0.0
        for t in transactions:
            net += t.amount
            if t.amount > 0:
                credits += t.amount
            else:
                debits += t.amount
        return TransactionTotals(credits=credits, debits=debits, net=net)

    def build_display_notes(self, transaction: Transaction) -> str:
        """Build a plain-text combined notes string from category, transfer, and user notes.

        Parts are joined with " | ". Rich markup is intentionally excluded;
        callers that need markup should wrap the result themselves.

        Returns an empty string when there is nothing to display.
        """
        note_parts: list[str] = []

        if transaction.category:
            cat_display = transaction.category
            if transaction.subcategory:
                cat_display += f":{transaction.subcategory}"
            note_parts.append(cat_display)

        try:
            transfer = transaction.metadata.get(TRANSFER_META_KEY)
            if isinstance(transfer, dict):
                role = transfer.get(TRANSFER_ROLE)
                cp_id = transfer.get(TRANSFER_COUNTERPARTY_ACCOUNT_ID)
                if cp_id:
                    cp_label = str(cp_id)
                    if role == ROLE_DEBIT:
                        note_parts.append(f"Transfer to {cp_label}")
                    elif role == ROLE_CREDIT:
                        note_parts.append(f"Transfer from {cp_label}")
                    else:
                        note_parts.append(f"Transfer {cp_label}")
        except (TypeError, KeyError):
            logger.debug("Failed to extract transfer metadata for display", exc_info=True)

        if transaction.notes:
            note_parts.append(transaction.notes)

        return " | ".join(note_parts) if note_parts else ""


__all__ = ["TransactionFilter", "TransactionQueryService", "TransactionTotals"]
