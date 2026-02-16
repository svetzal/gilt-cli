"""
Tests for event migration service - functional core for event sourcing migration.

Following pytest-bdd-style naming with arrange-act-assert pattern.
Tests cover:
- Transaction event generation from CSV
- Budget event generation from config
- Validation logic (projections vs original data)
- Error handling (invalid files, malformed data)
- Edge cases (empty files, missing fields)
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from pathlib import Path
from unittest.mock import Mock

import pytest

from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig
from gilt.model.events import BudgetCreated, TransactionCategorized, TransactionImported
from gilt.services.event_migration_service import EventMigrationService


@pytest.fixture
def sample_category_config() -> CategoryConfig:
    """Sample category configuration for testing."""
    return CategoryConfig(
        categories=[
            Category(
                name="Housing",
                description="Housing expenses",
                budget=Budget(amount=2000.0, period=BudgetPeriod.monthly),
            ),
            Category(
                name="Groceries",
                description="Food",
                budget=Budget(amount=500.0, period=BudgetPeriod.yearly),
            ),
            Category(
                name="Transportation",
                description="Transport",
                # No budget
            ),
        ]
    )


@pytest.fixture
def sample_csv_content() -> str:
    """Sample CSV ledger content."""
    return """transaction_id,date,description,amount,currency,account_id,counterparty,category,subcategory,notes,source_file,metadata,row_type
abc123,2025-01-15,Rent payment,-1500.00,CAD,CHQ,,Housing,Rent,,2025-01-13-mybank-chequing.csv,,primary
def456,2025-01-16,Grocery store,-85.50,CAD,MC,,Groceries,,,2025-01-13-mybank-cc.csv,,primary
ghi789,2025-01-17,Uncategorized,-50.00,CAD,CHQ,,,,,2025-01-13-mybank-chequing.csv,,primary
jkl012,2025-01-18,Duplicate transaction,-100.00,CAD,CHQ,,,,,,duplicate
"""


@pytest.fixture
def sample_csv_file(tmp_path: Path, sample_csv_content: str) -> Path:
    """Create temporary CSV file with sample content."""
    csv_path = tmp_path / "test_ledger.csv"
    csv_path.write_text(sample_csv_content)
    return csv_path


@pytest.fixture
def empty_csv_file(tmp_path: Path) -> Path:
    """Create empty CSV file with only headers."""
    csv_path = tmp_path / "empty_ledger.csv"
    csv_path.write_text("transaction_id,date,description,amount,currency,account_id,row_type\n")
    return csv_path


@pytest.fixture
def malformed_csv_file(tmp_path: Path) -> Path:
    """Create CSV file with malformed data."""
    csv_path = tmp_path / "malformed_ledger.csv"
    content = """transaction_id,date,description,amount,currency,account_id,row_type
abc123,2025-01-15,Test,not_a_number,CAD,CHQ,primary
def456,2025-01-16,Test,-100.00,CAD,MC,primary
"""
    csv_path.write_text(content)
    return csv_path


class DescribeGenerateTransactionEvents:
    """Tests for generate_transaction_events() method."""

    def it_should_generate_events_from_valid_csv(self, sample_csv_file: Path):
        """Should generate TransactionImported and TransactionCategorized events."""
        # Arrange
        service = EventMigrationService()

        # Act
        events, errors = service.generate_transaction_events(sample_csv_file)

        # Assert
        assert len(errors) == 0
        # 3 primary transactions: abc123 (imported + categorized), def456 (imported + categorized), ghi789 (imported only)
        assert len(events) == 5

        # Check first transaction (has category)
        tx_imported = events[0]
        assert isinstance(tx_imported, TransactionImported)
        assert tx_imported.transaction_id == "abc123"
        assert tx_imported.transaction_date == "2025-01-15"
        assert tx_imported.raw_description == "Rent payment"
        assert tx_imported.amount == Decimal("-1500.00")
        assert tx_imported.currency == "CAD"
        assert tx_imported.source_account == "CHQ"

        tx_categorized = events[1]
        assert isinstance(tx_categorized, TransactionCategorized)
        assert tx_categorized.transaction_id == "abc123"
        assert tx_categorized.category == "Housing"
        assert tx_categorized.subcategory == "Rent"
        assert tx_categorized.source == "user"

        # Check uncategorized transaction (no TransactionCategorized)
        uncategorized_event = events[4]
        assert isinstance(uncategorized_event, TransactionImported)
        assert uncategorized_event.transaction_id == "ghi789"

    def it_should_skip_non_primary_transactions(self, sample_csv_file: Path):
        """Should skip transactions with row_type != 'primary'."""
        # Arrange
        service = EventMigrationService()

        # Act
        events, errors = service.generate_transaction_events(sample_csv_file)

        # Assert
        # Should not include jkl012 (duplicate row_type)
        transaction_ids = [e.transaction_id for e in events if isinstance(e, TransactionImported)]
        assert "jkl012" not in transaction_ids
        assert len(transaction_ids) == 3  # Only primary transactions

    def it_should_handle_empty_csv(self, empty_csv_file: Path):
        """Should handle CSV with no data rows."""
        # Arrange
        service = EventMigrationService()

        # Act
        events, errors = service.generate_transaction_events(empty_csv_file)

        # Assert
        assert len(events) == 0
        assert len(errors) == 0

    def it_should_report_error_for_missing_transaction_id(self, tmp_path: Path):
        """Should report error when transaction_id is missing."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "no_id.csv"
        content = """transaction_id,date,description,amount,currency,account_id,row_type
,2025-01-15,Missing ID,-100.00,CAD,CHQ,primary
"""
        csv_path.write_text(content)

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(events) == 0
        assert len(errors) == 1
        assert "Missing transaction_id" in errors[0]

    def it_should_report_error_for_invalid_amount(self, malformed_csv_file: Path):
        """Should report error when amount is not a valid number."""
        # Arrange
        service = EventMigrationService()

        # Act
        events, errors = service.generate_transaction_events(malformed_csv_file)

        # Assert
        assert len(errors) >= 1
        assert any("malformed_ledger.csv" in e for e in errors)
        # Should still process valid second row
        assert len(events) == 1  # Only def456

    def it_should_handle_nonexistent_file(self, tmp_path: Path):
        """Should handle file not found gracefully."""
        # Arrange
        service = EventMigrationService()
        nonexistent = tmp_path / "nonexistent.csv"

        # Act
        events, errors = service.generate_transaction_events(nonexistent)

        # Assert
        assert len(events) == 0
        assert len(errors) == 1
        assert "not found" in errors[0].lower()

    def it_should_infer_timestamp_from_source_file(self, sample_csv_file: Path):
        """Should infer import timestamp from source filename."""
        # Arrange
        service = EventMigrationService()

        # Act
        events, errors = service.generate_transaction_events(sample_csv_file)

        # Assert
        tx_imported = events[0]
        assert isinstance(tx_imported, TransactionImported)
        # Source file is "2025-01-13-mybank-chequing.csv"
        assert tx_imported.event_timestamp.year == 2025
        assert tx_imported.event_timestamp.month == 1
        assert tx_imported.event_timestamp.day == 13
        assert tx_imported.event_timestamp.hour == 12  # Noon default

    def it_should_fallback_to_transaction_date_for_timestamp(self, tmp_path: Path):
        """Should use transaction date when source filename has no date."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "no-date-in-filename.csv"
        content = """transaction_id,date,description,amount,currency,account_id,source_file,row_type
abc123,2025-02-20,Test,-100.00,CAD,CHQ,import.csv,primary
"""
        csv_path.write_text(content)

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        tx_imported = events[0]
        assert isinstance(tx_imported, TransactionImported)
        # Should use transaction date (2025-02-20)
        assert tx_imported.event_timestamp.year == 2025
        assert tx_imported.event_timestamp.month == 2
        assert tx_imported.event_timestamp.day == 20

    def it_should_handle_missing_optional_fields(self, tmp_path: Path):
        """Should handle transactions with missing optional fields."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "minimal.csv"
        content = """transaction_id,date,description,amount,account_id,row_type
abc123,2025-01-15,Test,-100.00,CHQ,primary
"""
        csv_path.write_text(content)

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(errors) == 0
        assert len(events) == 1
        tx = events[0]
        assert isinstance(tx, TransactionImported)
        assert tx.currency == "CAD"  # Default
        assert tx.source_file == "minimal.csv"  # Filename fallback

    def it_should_handle_empty_string_category(self, tmp_path: Path):
        """Should not create TransactionCategorized for empty category."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "empty_cat.csv"
        content = """transaction_id,date,description,amount,currency,account_id,category,subcategory,row_type
abc123,2025-01-15,Test,-100.00,CAD,CHQ,,,primary
"""
        csv_path.write_text(content)

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(errors) == 0
        assert len(events) == 1  # Only TransactionImported, no TransactionCategorized
        assert isinstance(events[0], TransactionImported)

    def it_should_include_raw_data_in_imported_event(self, sample_csv_file: Path):
        """Should include complete CSV row in raw_data."""
        # Arrange
        service = EventMigrationService()

        # Act
        events, errors = service.generate_transaction_events(sample_csv_file)

        # Assert
        tx = events[0]
        assert isinstance(tx, TransactionImported)
        assert "date" in tx.raw_data
        assert "description" in tx.raw_data
        assert "amount" in tx.raw_data
        assert "account_id" in tx.raw_data
        assert tx.raw_data["date"] == "2025-01-15"


class DescribeGenerateBudgetEvents:
    """Tests for generate_budget_events() method."""

    def it_should_generate_budget_created_events(self, sample_category_config: CategoryConfig):
        """Should generate BudgetCreated event for each category with budget."""
        # Arrange
        service = EventMigrationService()

        # Act
        events = service.generate_budget_events(sample_category_config)

        # Assert
        assert len(events) == 2  # Housing and Groceries have budgets

        housing_event = events[0]
        assert isinstance(housing_event, BudgetCreated)
        assert housing_event.budget_id == "budget-housing"
        assert housing_event.category == "Housing"
        assert housing_event.subcategory is None
        assert housing_event.amount == Decimal("2000.0")
        assert housing_event.period_type == "monthly"
        assert housing_event.currency == "CAD"

        groceries_event = events[1]
        assert isinstance(groceries_event, BudgetCreated)
        assert groceries_event.budget_id == "budget-groceries"
        assert groceries_event.period_type == "yearly"

    def it_should_use_default_timestamp(self, sample_category_config: CategoryConfig):
        """Should use default timestamp of 2025-01-01 00:00:00."""
        # Arrange
        service = EventMigrationService()

        # Act
        events = service.generate_budget_events(sample_category_config)

        # Assert
        for event in events:
            assert event.event_timestamp == datetime(2025, 1, 1, 0, 0, 0)

    def it_should_use_custom_timestamp_when_provided(self, sample_category_config: CategoryConfig):
        """Should use custom timestamp when provided."""
        # Arrange
        service = EventMigrationService()
        custom_ts = datetime(2024, 6, 15, 14, 30, 0)

        # Act
        events = service.generate_budget_events(sample_category_config, timestamp=custom_ts)

        # Assert
        for event in events:
            assert event.event_timestamp == custom_ts

    def it_should_skip_categories_without_budget(self, sample_category_config: CategoryConfig):
        """Should not generate events for categories without budgets."""
        # Arrange
        service = EventMigrationService()

        # Act
        events = service.generate_budget_events(sample_category_config)

        # Assert
        # Transportation has no budget
        budget_ids = [e.budget_id for e in events if isinstance(e, BudgetCreated)]
        assert "budget-transportation" not in budget_ids

    def it_should_handle_empty_category_config(self):
        """Should handle category config with no categories."""
        # Arrange
        service = EventMigrationService()
        empty_config = CategoryConfig(categories=[])

        # Act
        events = service.generate_budget_events(empty_config)

        # Assert
        assert len(events) == 0

    def it_should_generate_deterministic_budget_ids(self, sample_category_config: CategoryConfig):
        """Should generate consistent budget IDs from category names."""
        # Arrange
        service = EventMigrationService()
        config = CategoryConfig(
            categories=[
                Category(
                    name="Entertainment & Fun",
                    budget=Budget(amount=100.0, period=BudgetPeriod.monthly),
                ),
            ]
        )

        # Act
        events = service.generate_budget_events(config)

        # Assert
        assert len(events) == 1
        # Should convert to lowercase and replace spaces
        event = events[0]
        assert isinstance(event, BudgetCreated)
        assert event.budget_id == "budget-entertainment-&-fun"

    def it_should_set_start_date_to_2025_01_01(self, sample_category_config: CategoryConfig):
        """Should set start_date to '2025-01-01' for all budgets."""
        # Arrange
        service = EventMigrationService()

        # Act
        events = service.generate_budget_events(sample_category_config)

        # Assert
        for event in events:
            assert isinstance(event, BudgetCreated)
            assert event.start_date == "2025-01-01"


class DescribeValidateMigration:
    """Tests for validate_migration() method."""

    def it_should_pass_validation_when_counts_match(
        self, tmp_path: Path, sample_category_config: CategoryConfig
    ):
        """Should pass validation when all counts match."""
        # Arrange
        service = EventMigrationService()

        # Create sample ledger
        data_dir = tmp_path / "data"
        data_dir.mkdir()
        ledger_path = data_dir / "test.csv"
        content = """transaction_id,date,description,amount,currency,account_id,category,row_type
abc123,2025-01-15,Test 1,-100.00,CAD,CHQ,Housing,primary
def456,2025-01-16,Test 2,-50.00,CAD,MC,Groceries,primary
"""
        ledger_path.write_text(content)

        # Mock builders
        mock_event_store = Mock()
        mock_tx_builder = Mock()
        mock_tx_builder.get_all_transactions.return_value = [
            {"transaction_id": "abc123", "transaction_date": "2025-01-15", "amount": "-100.00", "category": "Housing"},
            {"transaction_id": "def456", "transaction_date": "2025-01-16", "amount": "-50.00", "category": "Groceries"},
        ]
        mock_tx_builder.get_transaction.side_effect = lambda tid: (
            {"transaction_id": "abc123", "transaction_date": "2025-01-15", "amount": "-100.00", "category": "Housing"}
            if tid == "abc123"
            else {"transaction_id": "def456", "transaction_date": "2025-01-16", "amount": "-50.00", "category": "Groceries"}
        )

        mock_budget_builder = Mock()
        mock_budget_builder.get_active_budgets.return_value = [
            {"budget_id": "budget-housing"},
            {"budget_id": "budget-groceries"},
        ]

        # Act
        result = service.validate_migration(
            mock_event_store,
            data_dir,
            sample_category_config,
            mock_tx_builder,
            mock_budget_builder,
        )

        # Assert
        assert result.is_valid is True
        assert result.transaction_count_match is True
        assert result.budget_count_match is True
        assert result.sample_transactions_match is True
        assert len(result.errors) == 0

    def it_should_fail_when_transaction_count_mismatch(
        self, tmp_path: Path, sample_category_config: CategoryConfig
    ):
        """Should fail validation when transaction counts don't match."""
        # Arrange
        service = EventMigrationService()

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        ledger_path = data_dir / "test.csv"
        content = """transaction_id,date,description,amount,currency,account_id,row_type
abc123,2025-01-15,Test,-100.00,CAD,CHQ,primary
"""
        ledger_path.write_text(content)

        mock_event_store = Mock()
        mock_tx_builder = Mock()
        mock_tx_builder.get_all_transactions.return_value = []  # Empty projection
        mock_tx_builder.get_transaction.return_value = None

        mock_budget_builder = Mock()
        mock_budget_builder.get_active_budgets.return_value = [
            {"budget_id": "budget-housing"},
            {"budget_id": "budget-groceries"},
        ]

        # Act
        result = service.validate_migration(
            mock_event_store,
            data_dir,
            sample_category_config,
            mock_tx_builder,
            mock_budget_builder,
        )

        # Assert
        assert result.is_valid is False
        assert result.transaction_count_match is False
        assert len(result.errors) >= 1
        assert any("Transaction count mismatch" in e for e in result.errors)

    def it_should_fail_when_budget_count_mismatch(
        self, tmp_path: Path, sample_category_config: CategoryConfig
    ):
        """Should fail validation when budget counts don't match."""
        # Arrange
        service = EventMigrationService()

        data_dir = tmp_path / "data"
        data_dir.mkdir()

        mock_event_store = Mock()
        mock_tx_builder = Mock()
        mock_tx_builder.get_all_transactions.return_value = []
        mock_tx_builder.get_transaction.return_value = None

        mock_budget_builder = Mock()
        mock_budget_builder.get_active_budgets.return_value = []  # No budgets in projection

        # Act
        result = service.validate_migration(
            mock_event_store,
            data_dir,
            sample_category_config,
            mock_tx_builder,
            mock_budget_builder,
        )

        # Assert
        assert result.is_valid is False
        assert result.budget_count_match is False
        assert any("Budget count mismatch" in e for e in result.errors)

    def it_should_fail_when_sample_transaction_fields_mismatch(
        self, tmp_path: Path, sample_category_config: CategoryConfig
    ):
        """Should fail validation when transaction fields don't match."""
        # Arrange
        service = EventMigrationService()

        data_dir = tmp_path / "data"
        data_dir.mkdir()
        ledger_path = data_dir / "test.csv"
        content = """transaction_id,date,description,amount,currency,account_id,category,row_type
abc123,2025-01-15,Test,-100.00,CAD,CHQ,Housing,primary
"""
        ledger_path.write_text(content)

        mock_event_store = Mock()
        mock_tx_builder = Mock()
        mock_tx_builder.get_all_transactions.return_value = [
            {"transaction_id": "abc123"},
        ]
        # Return mismatched data
        mock_tx_builder.get_transaction.return_value = {
            "transaction_id": "abc123",
            "transaction_date": "2025-01-16",  # Wrong date
            "amount": "-100.00",
            "category": "Housing",
        }

        mock_budget_builder = Mock()
        mock_budget_builder.get_active_budgets.return_value = [
            {"budget_id": "budget-housing"},
            {"budget_id": "budget-groceries"},
        ]

        # Act
        result = service.validate_migration(
            mock_event_store,
            data_dir,
            sample_category_config,
            mock_tx_builder,
            mock_budget_builder,
        )

        # Assert
        assert result.is_valid is False
        assert result.sample_transactions_match is False
        assert any("date mismatch" in e for e in result.errors)

    def it_should_handle_missing_data_directory(self, sample_category_config: CategoryConfig):
        """Should handle missing data directory gracefully."""
        # Arrange
        service = EventMigrationService()
        nonexistent_dir = Path("/nonexistent/directory")

        mock_event_store = Mock()
        mock_tx_builder = Mock()
        mock_tx_builder.get_all_transactions.return_value = []
        mock_tx_builder.get_transaction.return_value = None

        mock_budget_builder = Mock()
        mock_budget_builder.get_active_budgets.return_value = []

        # Act
        result = service.validate_migration(
            mock_event_store,
            nonexistent_dir,
            sample_category_config,
            mock_tx_builder,
            mock_budget_builder,
        )

        # Assert
        assert result.transaction_count_match is True  # 0 == 0
        assert result.budget_count_match is False  # 2 != 0


class DescribeInferImportTimestamp:
    """Tests for _infer_import_timestamp() helper method."""

    def it_should_extract_date_from_standard_filename(self):
        """Should extract date from filename format YYYY-MM-DD-*."""
        # Arrange
        service = EventMigrationService()

        # Act
        timestamp = service._infer_import_timestamp(
            "2025-08-21-mybank-chequing.csv", "2025-08-15"
        )

        # Assert
        assert timestamp.year == 2025
        assert timestamp.month == 8
        assert timestamp.day == 21
        assert timestamp.hour == 12
        assert timestamp.minute == 0

    def it_should_fallback_to_transaction_date(self):
        """Should use transaction date when filename has no date."""
        # Arrange
        service = EventMigrationService()

        # Act
        timestamp = service._infer_import_timestamp("import.csv", "2025-09-15")

        # Assert
        assert timestamp.year == 2025
        assert timestamp.month == 9
        assert timestamp.day == 15
        assert timestamp.hour == 12

    def it_should_handle_invalid_filename_and_date(self):
        """Should return current time when both filename and date are invalid."""
        # Arrange
        service = EventMigrationService()
        now_before = datetime.now()

        # Act
        timestamp = service._infer_import_timestamp("invalid.csv", "not-a-date")

        # Assert
        now_after = datetime.now()
        assert now_before <= timestamp <= now_after


class DescribeEdgeCases:
    """Tests for edge cases and boundary conditions."""

    def it_should_handle_csv_with_extra_columns(self, tmp_path: Path):
        """Should handle CSV with extra columns not in row dict."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "extra_cols.csv"
        content = """transaction_id,date,description,amount,currency,account_id,row_type,extra_field
abc123,2025-01-15,Test,-100.00,CAD,CHQ,primary,ignored
"""
        csv_path.write_text(content)

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(errors) == 0
        assert len(events) == 1

    def it_should_handle_csv_with_unicode_characters(self, tmp_path: Path):
        """Should handle CSV with unicode characters in descriptions."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "unicode.csv"
        content = """transaction_id,date,description,amount,currency,account_id,row_type
abc123,2025-01-15,Café Déjà vu 🎉,-100.00,CAD,CHQ,primary
"""
        csv_path.write_text(content, encoding="utf-8")

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(errors) == 0
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionImported)
        assert event.raw_description == "Café Déjà vu 🎉"

    def it_should_preserve_decimal_precision(self, tmp_path: Path):
        """Should preserve decimal precision for amounts."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "precision.csv"
        content = """transaction_id,date,description,amount,currency,account_id,row_type
abc123,2025-01-15,Test,-123.456789,CAD,CHQ,primary
"""
        csv_path.write_text(content)

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(errors) == 0
        event = events[0]
        assert isinstance(event, TransactionImported)
        assert isinstance(event.amount, Decimal)
        assert event.amount == Decimal("-123.456789")

    def it_should_handle_large_csv_files(self, tmp_path: Path):
        """Should handle CSV with many rows efficiently."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "large.csv"

        # Generate 1000 rows
        lines = ["transaction_id,date,description,amount,currency,account_id,row_type"]
        for i in range(1000):
            lines.append(f"txn{i:05d},2025-01-15,Test {i},-{i}.00,CAD,CHQ,primary")
        csv_path.write_text("\n".join(lines))

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(errors) == 0
        assert len(events) == 1000  # All TransactionImported (no categories)

    def it_should_handle_whitespace_in_transaction_ids(self, tmp_path: Path):
        """Should strip whitespace from transaction IDs."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "whitespace.csv"
        content = """transaction_id,date,description,amount,currency,account_id,row_type
  abc123  ,2025-01-15,Test,-100.00,CAD,CHQ,primary
"""
        csv_path.write_text(content)

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(errors) == 0
        assert len(events) == 1
        event = events[0]
        assert isinstance(event, TransactionImported)
        assert event.transaction_id == "abc123"

    def it_should_handle_whitespace_in_categories(self, tmp_path: Path):
        """Should strip whitespace from category names."""
        # Arrange
        service = EventMigrationService()
        csv_path = tmp_path / "cat_whitespace.csv"
        content = """transaction_id,date,description,amount,currency,account_id,category,subcategory,row_type
abc123,2025-01-15,Test,-100.00,CAD,CHQ,  Housing  ,  Rent  ,primary
"""
        csv_path.write_text(content)

        # Act
        events, errors = service.generate_transaction_events(csv_path)

        # Assert
        assert len(events) == 2
        cat_event = events[1]
        assert isinstance(cat_event, TransactionCategorized)
        assert cat_event.category == "Housing"
        assert cat_event.subcategory == "Rent"
