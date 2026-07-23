from __future__ import annotations

"""
Transaction Service - Business logic for transaction operations

Handles loading, filtering, and manipulating transaction data for the GUI.
All operations remain local-only with no network I/O.
"""

import logging
from datetime import date, timedelta
from pathlib import Path

from gilt.model.account import TransactionGroup
from gilt.model.ledger_repository import LEDGER_IO_ERRORS, LedgerRepository
from gilt.services.transaction_query_service import TransactionFilter, TransactionQueryService
from gilt.storage.projection import ProjectionBuilder

logger = logging.getLogger(__name__)


def get_date_range(selection: str, today: date) -> tuple[date | None, date | None]:
    """Compute (start_date, end_date) from a date range preset selection.

    Returns (None, None) for unrecognized selections (including 'All' and 'Custom').
    """
    if selection == "This Month":
        return date(today.year, today.month, 1), today
    if selection == "Last Month":
        first_of_current = date(today.year, today.month, 1)
        end = first_of_current - timedelta(days=1)
        return date(end.year, end.month, 1), end
    if selection == "This Year":
        return date(today.year, 1, 1), today
    if selection == "Last Year":
        return date(today.year - 1, 1, 1), date(today.year - 1, 12, 31)
    return None, None


class TransactionService:
    """Service for managing transaction data operations."""

    def __init__(self, data_dir: Path, projections_db_path: Path | None = None):
        """
        Initialize transaction service.

        Args:
            data_dir: Path to directory containing ledger CSV files
            projections_db_path: Path to projections SQLite database.
                Defaults to data_dir.parent / 'projections.db'.
        """
        self.data_dir = Path(data_dir)
        if projections_db_path is None:
            self.projections_db_path = self.data_dir.parent / "projections.db"
        else:
            self.projections_db_path = Path(projections_db_path)
        self._ledger_repo = LedgerRepository(self.data_dir)
        self._cache: dict[str, list[TransactionGroup]] = {}

    def load_all_transactions(self, include_duplicates: bool = False) -> list[TransactionGroup]:
        """
        Load all transactions from the projections database.

        Falls back to CSV files if the projections database does not exist.

        Args:
            include_duplicates: Whether to include duplicate-flagged transactions

        Returns:
            List of all transaction groups across all accounts
        """
        if self.projections_db_path.exists():
            return self._load_from_projections(include_duplicates)
        return self._load_from_csv()

    def _load_from_projections(self, include_duplicates: bool = False) -> list[TransactionGroup]:
        """Load transactions from the projections database."""
        projection_builder = ProjectionBuilder(self.projections_db_path)
        rows = projection_builder.get_all_transactions(include_duplicates=include_duplicates)
        return [TransactionGroup.from_projection_row(row) for row in rows]

    def _load_from_csv(self, default_currency: str = "CAD") -> list[TransactionGroup]:
        """Load transactions from CSV ledger files (fallback)."""
        return self._ledger_repo.load_all()

    def load_account_transactions(
        self, account_id: str, default_currency: str = "CAD"
    ) -> list[TransactionGroup]:
        """
        Load transactions for a specific account.

        Args:
            account_id: Account identifier (e.g., "MYBANK_CHQ")
            default_currency: Fallback currency for legacy rows

        Returns:
            List of transaction groups for the account
        """
        # Check cache first
        if account_id in self._cache:
            return self._cache[account_id]

        if not self._ledger_repo.exists(account_id):
            return []

        try:
            groups = self._ledger_repo.load(account_id)
            self._cache[account_id] = groups
            return groups
        except LEDGER_IO_ERRORS as e:
            logger.error("Failed to load account %s: %s", account_id, e, exc_info=True)
            return []

    def load_available_accounts(self) -> list[str]:
        """
        Load list of available account IDs.

        Uses projections database if available, falls back to ledger file names.

        Returns:
            Sorted list of account IDs
        """
        if self.projections_db_path.exists():
            return ProjectionBuilder(self.projections_db_path).get_distinct_account_ids()

        return self._ledger_repo.available_account_ids()

    def find_transactions(
        self,
        transactions: list[TransactionGroup],
        account_filter: list[str] | None = None,
        start_date: date | None = None,
        end_date: date | None = None,
        min_amount: float | None = None,
        max_amount: float | None = None,
        category_filter: list[str] | None = None,
        search_text: str | None = None,
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
        criteria = TransactionFilter(
            account_ids=tuple(account_filter) if account_filter else None,
            date_start=start_date,
            date_end=end_date,
            min_abs_amount=min_amount,
            max_abs_amount=max_amount,
            categories=tuple(category_filter) if category_filter else None,
            uncategorized_only=uncategorized_only,
            search_text=search_text or None,
        )
        by_id = {g.primary.transaction_id: g for g in transactions}
        matched = TransactionQueryService().find_matching(
            [g.primary for g in transactions], criteria
        )
        return [by_id[t.transaction_id] for t in matched]

    def clear_cache(self):
        """Clear the transaction cache."""
        self._cache.clear()

    def get_unique_categories(self, transactions: list[TransactionGroup]) -> list[str]:
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

    def delete_transaction(self, transaction_id: str, account_id: str) -> bool:
        """
        Delete a transaction from the ledger.

        Args:
            transaction_id: ID of transaction to delete
            account_id: Account ID (to locate the file)

        Returns:
            True if successful, False otherwise
        """
        if not self._ledger_repo.exists(account_id):
            return False

        try:
            groups = self._ledger_repo.load(account_id)

            # Filter out the transaction
            new_groups = [g for g in groups if g.primary.transaction_id != transaction_id]

            if len(new_groups) == len(groups):
                return False  # Transaction not found

            self._ledger_repo.save(account_id, new_groups)

            # Clear cache for this account
            if account_id in self._cache:
                del self._cache[account_id]

            return True

        except LEDGER_IO_ERRORS as e:
            logger.error("Failed to delete transaction %s: %s", transaction_id, e, exc_info=True)
            return False

    def update_transaction(self, group: TransactionGroup) -> bool:
        """
        Update a transaction in the ledger.

        Args:
            group: The updated transaction group.

        Returns:
            True if successful.
        """
        account_id = group.primary.account_id
        if not self._ledger_repo.exists(account_id):
            return False

        try:
            groups = self._ledger_repo.load(account_id)

            # Find and replace
            found = False
            for i, g in enumerate(groups):
                if g.primary.transaction_id == group.primary.transaction_id:
                    groups[i] = group
                    found = True
                    break

            if not found:
                return False

            self._ledger_repo.save(account_id, groups)

            # Clear cache
            if account_id in self._cache:
                del self._cache[account_id]

            return True

        except LEDGER_IO_ERRORS as e:
            logger.error("Failed to update transaction: %s", e, exc_info=True)
            return False
