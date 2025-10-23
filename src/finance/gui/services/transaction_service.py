from __future__ import annotations

"""
Transaction Service - Business logic for transaction operations

Handles loading, filtering, and manipulating transaction data for the GUI.
All operations remain local-only with no network I/O.
"""

from pathlib import Path
from typing import Optional
from datetime import date

from finance.model.ledger_io import load_ledger_csv
from finance.model.account import TransactionGroup


class TransactionService:
    """Service for managing transaction data operations."""

    def __init__(self, data_dir: Path):
        """
        Initialize transaction service.

        Args:
            data_dir: Path to directory containing ledger CSV files
        """
        self.data_dir = Path(data_dir)
        self._cache: dict[str, list[TransactionGroup]] = {}

    def load_all_transactions(
        self, default_currency: str = "CAD"
    ) -> list[TransactionGroup]:
        """
        Load transactions from all ledger files in data directory.

        Args:
            default_currency: Fallback currency for legacy rows

        Returns:
            List of all transaction groups across all accounts
        """
        all_transactions: list[TransactionGroup] = []

        if not self.data_dir.exists():
            return all_transactions

        for ledger_file in sorted(self.data_dir.glob("*.csv")):
            try:
                text = ledger_file.read_text(encoding="utf-8")
                groups = load_ledger_csv(text, default_currency=default_currency)
                all_transactions.extend(groups)
            except Exception as e:
                # Log error but continue with other files
                print(f"Error loading {ledger_file.name}: {e}")
                continue

        return all_transactions

    def load_account_transactions(
        self, account_id: str, default_currency: str = "CAD"
    ) -> list[TransactionGroup]:
        """
        Load transactions for a specific account.

        Args:
            account_id: Account identifier (e.g., "RBC_CHQ")
            default_currency: Fallback currency for legacy rows

        Returns:
            List of transaction groups for the account
        """
        # Check cache first
        if account_id in self._cache:
            return self._cache[account_id]

        ledger_path = self.data_dir / f"{account_id}.csv"
        if not ledger_path.exists():
            return []

        try:
            text = ledger_path.read_text(encoding="utf-8")
            groups = load_ledger_csv(text, default_currency=default_currency)
            self._cache[account_id] = groups
            return groups
        except Exception as e:
            print(f"Error loading account {account_id}: {e}")
            return []

    def get_available_accounts(self) -> list[str]:
        """
        Get list of available account IDs from ledger files.

        Returns:
            List of account IDs (without .csv extension)
        """
        if not self.data_dir.exists():
            return []

        return sorted([f.stem for f in self.data_dir.glob("*.csv")])

    def filter_transactions(
        self,
        transactions: list[TransactionGroup],
        account_filter: Optional[list[str]] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        min_amount: Optional[float] = None,
        max_amount: Optional[float] = None,
        category_filter: Optional[list[str]] = None,
        search_text: Optional[str] = None,
        uncategorized_only: bool = False,
    ) -> list[TransactionGroup]:
        """
        Filter transactions based on criteria.

        Args:
            transactions: List of transactions to filter
            account_filter: List of account IDs to include
            start_date: Filter transactions on or after this date
            end_date: Filter transactions on or before this date
            min_amount: Minimum absolute amount
            max_amount: Maximum absolute amount
            category_filter: List of categories to include
            search_text: Search in description and counterparty (case-insensitive)
            uncategorized_only: Show only transactions without categories

        Returns:
            Filtered list of transaction groups
        """
        filtered = transactions

        # Account filter
        if account_filter:
            filtered = [
                g for g in filtered if g.primary.account_id in account_filter
            ]

        # Date range filter
        if start_date:
            filtered = [g for g in filtered if g.primary.date >= start_date]
        if end_date:
            filtered = [g for g in filtered if g.primary.date <= end_date]

        # Amount range filter
        if min_amount is not None:
            filtered = [
                g for g in filtered if abs(g.primary.amount) >= min_amount
            ]
        if max_amount is not None:
            filtered = [
                g for g in filtered if abs(g.primary.amount) <= max_amount
            ]

        # Category filter
        if category_filter:
            filtered = [
                g for g in filtered
                if g.primary.category in category_filter
            ]

        # Uncategorized filter
        if uncategorized_only:
            filtered = [
                g for g in filtered
                if not g.primary.category or g.primary.category.strip() == ""
            ]

        # Search text filter
        if search_text:
            search_lower = search_text.lower()
            filtered = [
                g for g in filtered
                if (
                    search_lower in (g.primary.description or "").lower()
                    or search_lower in (g.primary.counterparty or "").lower()
                )
            ]

        return filtered

    def clear_cache(self):
        """Clear the transaction cache."""
        self._cache.clear()

    def get_unique_categories(
        self, transactions: list[TransactionGroup]
    ) -> list[str]:
        """
        Extract unique categories from transactions.

        Args:
            transactions: List of transaction groups

        Returns:
            Sorted list of unique category names
        """
        categories = set()
        for group in transactions:
            if group.primary.category:
                categories.add(group.primary.category)
        return sorted(categories)
