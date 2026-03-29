from __future__ import annotations

"""
Transaction Query Service - pure filtering and aggregation logic.

Accepts Transaction objects directly; no file I/O, no projections database,
no UI imports (rich, typer, PySide6).
"""

import logging
from dataclasses import dataclass

from gilt.model.account import Transaction
from gilt.transfer import (
    ROLE_CREDIT,
    ROLE_DEBIT,
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_META_KEY,
    TRANSFER_ROLE,
)

logger = logging.getLogger(__name__)


@dataclass
class TransactionTotals:
    """Aggregated credit, debit, and net amounts for a set of transactions."""

    credits: float
    debits: float
    net: float


class TransactionQueryService:
    """Pure business logic for filtering and querying transactions.

    All methods accept Transaction objects directly and return plain data.
    No I/O, no UI imports.
    """

    def filter_transactions(
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
        result = [
            t
            for t in transactions
            if t.account_id == account_id and (year is None or t.date.year == year)
        ]
        result.sort(key=lambda t: (t.date, t.transaction_id))
        if limit is not None:
            result = result[:limit]
        return result

    def calculate_totals(self, transactions: list[Transaction]) -> TransactionTotals:
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
        except Exception:
            logger.debug("Failed to extract transfer metadata for display", exc_info=True)

        if transaction.notes:
            note_parts.append(transaction.notes)

        return " | ".join(note_parts) if note_parts else ""


__all__ = ["TransactionQueryService", "TransactionTotals"]
