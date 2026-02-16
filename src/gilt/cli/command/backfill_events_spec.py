"""
Tests for event backfill migration tool.

Validates that events can be correctly generated from existing data
and that projections rebuilt from events match the original data.
"""
from __future__ import annotations

import tempfile
from pathlib import Path
from decimal import Decimal
import csv

import pytest

from gilt.cli.command import backfill_events
from gilt.model.events import BudgetCreated, TransactionImported, TransactionCategorized
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


class DescribeBackfillEvents:
    """Test suite for backfill events migration tool."""

    @pytest.fixture
    def temp_dir(self):
        """Create temporary directory for test data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def test_ledger(self, temp_dir):
        """Create a test ledger CSV file."""
        ledger_dir = temp_dir / "data" / "accounts"
        ledger_dir.mkdir(parents=True)
        ledger_path = ledger_dir / "test_account.csv"

        with open(ledger_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            # Write header
            writer.writerow([
                'row_type', 'group_id', 'transaction_id', 'date', 'description',
                'amount', 'currency', 'account_id', 'counterparty', 'category',
                'subcategory', 'notes', 'source_file', 'metadata_json', 'line_id',
                'target_account_id', 'split_category', 'split_subcategory',
                'split_memo', 'split_percent'
            ])
            # Write test transactions
            writer.writerow([
                'primary', 'abc123', 'abc123', '2025-01-15', 'Test Transaction 1',
                '-50.00', 'CAD', 'TEST_ACCT', '', 'Groceries', '', '',
                '2025-01-20-test.csv', '{}', '', '', '', '', '', ''
            ])
            writer.writerow([
                'primary', 'def456', 'def456', '2025-01-16', 'Test Transaction 2',
                '-100.00', 'CAD', 'TEST_ACCT', '', '', '', '',
                '2025-01-20-test.csv', '{}', '', '', '', '', '', ''
            ])
            writer.writerow([
                'primary', 'ghi789', 'ghi789', '2025-01-17', 'Test Transaction 3',
                '200.00', 'CAD', 'TEST_ACCT', '', 'Housing', 'Utilities', '',
                '2025-01-20-test.csv', '{}', '', '', '', '', '', ''
            ])

        return ledger_path

    @pytest.fixture
    def test_categories(self, temp_dir):
        """Create a test categories.yml file."""
        config_dir = temp_dir / "config"
        config_dir.mkdir(parents=True)
        categories_path = config_dir / "categories.yml"

        content = """categories:
  - name: "Groceries"
    description: "Food and household supplies"
    budget:
      amount: 500.00
      period: monthly

  - name: "Housing"
    description: "Housing expenses"
    subcategories:
      - name: "Utilities"
        description: "Electric, water, etc"
    budget:
      amount: 1500.00
      period: monthly
"""
        categories_path.write_text(content, encoding='utf-8')
        return categories_path

    def it_should_run_dry_run_without_errors(self, temp_dir, test_ledger, test_categories):
        """Test that dry run mode works without writing events."""
        # Arrange
        workspace = Workspace(root=temp_dir)
        event_store_path = temp_dir / "events.db"
        projections_path = temp_dir / "projections.db"
        budget_projections_path = temp_dir / "budget_projections.db"

        # Act
        result = backfill_events.run(
            workspace=workspace,
            event_store_path=event_store_path,
            projections_db_path=projections_path,
            budget_projections_db_path=budget_projections_path,
            dry_run=True,
        )

        # Assert
        assert result == 0
        # EventStore creates DB on init, but events shouldn't be written in dry run
        if event_store_path.exists():
            event_store = EventStore(str(event_store_path))
            all_events = event_store.get_all_events()
            assert len(all_events) == 0, "Dry run should not write events"

    def it_should_backfill_transaction_events(self, temp_dir, test_ledger, test_categories):
        """Test that transaction events are correctly backfilled."""
        # Arrange
        workspace = Workspace(root=temp_dir)
        event_store_path = temp_dir / "events.db"
        projections_path = temp_dir / "projections.db"
        budget_projections_path = temp_dir / "budget_projections.db"

        # Act
        result = backfill_events.run(
            workspace=workspace,
            event_store_path=event_store_path,
            projections_db_path=projections_path,
            budget_projections_db_path=budget_projections_path,
            dry_run=False,
        )

        # Assert
        assert result == 0
        assert event_store_path.exists()

        # Verify events were created
        event_store = EventStore(str(event_store_path))
        imported_events = event_store.get_events_by_type("TransactionImported")
        assert len(imported_events) == 3

        categorized_events = event_store.get_events_by_type("TransactionCategorized")
        assert len(categorized_events) == 2  # Only 2 transactions have categories

    def it_should_backfill_budget_events(self, temp_dir, test_ledger, test_categories):
        """Test that budget events are correctly backfilled."""
        # Arrange
        workspace = Workspace(root=temp_dir)
        event_store_path = temp_dir / "events.db"
        projections_path = temp_dir / "projections.db"
        budget_projections_path = temp_dir / "budget_projections.db"

        # Act
        result = backfill_events.run(
            workspace=workspace,
            event_store_path=event_store_path,
            projections_db_path=projections_path,
            budget_projections_db_path=budget_projections_path,
            dry_run=False,
        )

        # Assert
        assert result == 0

        # Verify budget events were created
        event_store = EventStore(str(event_store_path))
        budget_events = event_store.get_events_by_type("BudgetCreated")
        assert len(budget_events) == 2  # Two categories with budgets

        # Verify budget details
        groceries_budget = next(
            (
                e for e in budget_events
                if isinstance(e, BudgetCreated) and e.category == "Groceries"
            ),
            None
        )
        assert groceries_budget is not None
        assert isinstance(groceries_budget, BudgetCreated)
        assert groceries_budget.amount == Decimal("500.00")
        assert groceries_budget.period_type == "monthly"

    def it_should_validate_projections_match_original_data(
        self, temp_dir, test_ledger, test_categories
    ):
        """Test that projections rebuilt from events match original data."""
        # Arrange
        workspace = Workspace(root=temp_dir)
        event_store_path = temp_dir / "events.db"
        projections_path = temp_dir / "projections.db"
        budget_projections_path = temp_dir / "budget_projections.db"

        # Act
        result = backfill_events.run(
            workspace=workspace,
            event_store_path=event_store_path,
            projections_db_path=projections_path,
            budget_projections_db_path=budget_projections_path,
            dry_run=False,
        )

        # Assert - validation should pass
        assert result == 0

        # Verify projections exist and have correct data
        tx_builder = ProjectionBuilder(projections_path)
        transactions = tx_builder.get_all_transactions(include_duplicates=False)
        assert len(transactions) == 3

        # Verify specific transaction
        tx = tx_builder.get_transaction('abc123')
        assert tx is not None
        assert tx['transaction_date'] == '2025-01-15'
        assert float(tx['amount']) == -50.00
        assert tx['category'] == 'Groceries'

    def it_should_preserve_categorization_data(
        self, temp_dir, test_ledger, test_categories
    ):
        """Test that existing categorizations are preserved in events."""
        # Arrange
        workspace = Workspace(root=temp_dir)
        event_store_path = temp_dir / "events.db"
        projections_path = temp_dir / "projections.db"
        budget_projections_path = temp_dir / "budget_projections.db"

        # Act
        backfill_events.run(
            workspace=workspace,
            event_store_path=event_store_path,
            projections_db_path=projections_path,
            budget_projections_db_path=budget_projections_path,
            dry_run=False,
        )

        # Assert
        event_store = EventStore(str(event_store_path))
        categorized_events = event_store.get_events_by_type("TransactionCategorized")

        # Find categorization for transaction with subcategory
        housing_cat = next(
            (
                e for e in categorized_events
                if isinstance(e, TransactionCategorized) and e.category == "Housing"
            ),
            None
        )
        assert housing_cat is not None
        assert isinstance(housing_cat, TransactionCategorized)
        assert housing_cat.subcategory == "Utilities"
        assert housing_cat.source == "user"

    def it_should_handle_uncategorized_transactions(
        self, temp_dir, test_ledger, test_categories
    ):
        """Test that uncategorized transactions don't generate categorization events."""
        # Arrange
        workspace = Workspace(root=temp_dir)
        event_store_path = temp_dir / "events.db"
        projections_path = temp_dir / "projections.db"
        budget_projections_path = temp_dir / "budget_projections.db"

        # Act
        backfill_events.run(
            workspace=workspace,
            event_store_path=event_store_path,
            projections_db_path=projections_path,
            budget_projections_db_path=budget_projections_path,
            dry_run=False,
        )

        # Assert
        event_store = EventStore(str(event_store_path))

        # Should have 3 TransactionImported events
        imported = event_store.get_events_by_type("TransactionImported")
        assert len(imported) == 3

        # But only 2 TransactionCategorized events (one transaction is uncategorized)
        categorized = event_store.get_events_by_type("TransactionCategorized")
        assert len(categorized) == 2

    def it_should_use_source_file_timestamp(
        self, temp_dir, test_ledger, test_categories
    ):
        """Test that event timestamps are inferred from source filenames."""
        # Arrange
        workspace = Workspace(root=temp_dir)
        event_store_path = temp_dir / "events.db"
        projections_path = temp_dir / "projections.db"
        budget_projections_path = temp_dir / "budget_projections.db"

        # Act
        backfill_events.run(
            workspace=workspace,
            event_store_path=event_store_path,
            projections_db_path=projections_path,
            budget_projections_db_path=budget_projections_path,
            dry_run=False,
        )

        # Assert
        event_store = EventStore(str(event_store_path))
        imported_events = event_store.get_events_by_type("TransactionImported")

        # Verify timestamp is inferred from source file (2025-01-20-test.csv)
        for event in imported_events:
            assert event.event_timestamp.year == 2025
            assert event.event_timestamp.month == 1
            assert event.event_timestamp.day == 20

    def it_should_skip_non_primary_transactions(self, temp_dir, test_categories):
        """Test that only primary transactions are backfilled."""
        # Arrange
        ledger_dir = temp_dir / "data" / "accounts"
        ledger_dir.mkdir(parents=True, exist_ok=True)
        ledger_path = ledger_dir / "test.csv"
        with open(ledger_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                'row_type', 'group_id', 'transaction_id', 'date', 'description',
                'amount', 'currency', 'account_id', 'counterparty', 'category',
                'subcategory', 'notes', 'source_file', 'metadata_json', 'line_id',
                'target_account_id', 'split_category', 'split_subcategory',
                'split_memo', 'split_percent'
            ])
            # Primary transaction
            writer.writerow([
                'primary', 'abc123', 'abc123', '2025-01-15', 'Primary',
                '-50.00', 'CAD', 'TEST', '', '', '', '',
                '2025-01-20-test.csv', '{}', '', '', '', '', '', ''
            ])
            # Duplicate (should be skipped)
            writer.writerow([
                'duplicate', 'abc123', 'abc124', '2025-01-15', 'Duplicate',
                '-50.00', 'CAD', 'TEST', '', '', '', '',
                '2025-01-20-test.csv', '{}', '', '', '', '', '', ''
            ])

        workspace = Workspace(root=temp_dir)
        event_store_path = temp_dir / "events.db"
        projections_path = temp_dir / "projections.db"
        budget_projections_path = temp_dir / "budget_projections.db"

        # Act
        backfill_events.run(
            workspace=workspace,
            event_store_path=event_store_path,
            projections_db_path=projections_path,
            budget_projections_db_path=budget_projections_path,
            dry_run=False,
        )

        # Assert - only 1 event (primary), not 2
        event_store = EventStore(str(event_store_path))
        imported_events = event_store.get_events_by_type("TransactionImported")
        assert len(imported_events) == 1
        event = imported_events[0]
        assert isinstance(event, TransactionImported)
        assert event.transaction_id == 'abc123'
