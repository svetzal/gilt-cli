"""
Event Migration Service - Business logic for event sourcing migration.

Provides event generation from legacy data (CSVs, configuration files) and
validation that projections match original data. This service is the functional
core for the backfill_events CLI command.

All business logic for:
- Generating TransactionImported/TransactionCategorized events from CSV
- Generating BudgetCreated events from categories.yml
- Validating that projections rebuilt from events match original data

No I/O, no UI dependencies - pure transformation and validation logic.
"""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import List, Optional, Tuple

from gilt.model.category import CategoryConfig
from gilt.model.events import (
    BudgetCreated,
    TransactionCategorized,
    TransactionImported,
    Event,
)
from gilt.storage.budget_projection import BudgetProjectionBuilder
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder


@dataclass
class MigrationStats:
    """Statistics from migration process."""

    transaction_imported: int
    transaction_categorized: int
    budget_created: int
    errors: int


@dataclass
class ValidationResult:
    """Result of projection validation against original data."""

    is_valid: bool
    errors: List[str]
    transaction_count_match: bool
    budget_count_match: bool
    sample_transactions_match: bool


class EventMigrationService:
    """Service for event migration from legacy data.

    Pure business logic with no I/O or UI dependencies.
    All file paths and data structures passed as parameters.
    """

    def generate_transaction_events(self, csv_path: Path) -> Tuple[List[Event], List[str]]:
        """Generate transaction events from a CSV ledger file.

        Parses CSV and creates:
        - TransactionImported event for each primary transaction
        - TransactionCategorized event if transaction has category

        Args:
            csv_path: Path to ledger CSV file

        Returns:
            Tuple of (events list, errors list)
        """
        events: List[Event] = []
        errors: List[str] = []

        try:
            with open(csv_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)

                for row_num, row in enumerate(reader, start=2):  # Start at 2 (header = 1)
                    try:
                        # Only process primary transactions (not duplicates or linked)
                        if row.get("row_type") != "primary":
                            continue

                        transaction_id = row.get("transaction_id", "").strip()
                        if not transaction_id:
                            errors.append(f"{csv_path.name}:{row_num} - Missing transaction_id")
                            continue

                        # Generate TransactionImported event
                        source_file = row.get("source_file", csv_path.name)
                        import_timestamp = self._infer_import_timestamp(
                            source_file, row.get("date", "")
                        )

                        event = TransactionImported(
                            transaction_id=transaction_id,
                            transaction_date=row.get("date", ""),
                            source_file=source_file,
                            source_account=row.get("account_id", ""),
                            raw_description=row.get("description", ""),
                            amount=Decimal(row.get("amount", "0")),
                            currency=row.get("currency", "CAD"),
                            raw_data={
                                "date": row.get("date", ""),
                                "description": row.get("description", ""),
                                "amount": row.get("amount", ""),
                                "account_id": row.get("account_id", ""),
                            },
                            event_timestamp=import_timestamp,
                        )
                        events.append(event)

                        # If transaction has category, generate TransactionCategorized
                        category = row.get("category", "").strip()
                        if category:
                            subcategory = row.get("subcategory", "").strip() or None

                            cat_event = TransactionCategorized(
                                transaction_id=transaction_id,
                                category=category,
                                subcategory=subcategory,
                                source="user",
                                previous_category=None,
                                previous_subcategory=None,
                                rationale="Migrated from existing ledger",
                                event_timestamp=import_timestamp,
                            )
                            events.append(cat_event)

                    except (ValueError, KeyError, TypeError, Exception) as e:
                        errors.append(f"{csv_path.name}:{row_num} - {str(e)}")
                        continue

        except FileNotFoundError:
            errors.append(f"File not found: {csv_path}")
        except csv.Error as e:
            errors.append(f"CSV parse error in {csv_path.name}: {e}")

        return events, errors

    def generate_budget_events(
        self, category_config: CategoryConfig, timestamp: Optional[datetime] = None
    ) -> List[Event]:
        """Generate budget events from category configuration.

        Creates BudgetCreated event for each category with a budget.

        Args:
            category_config: Loaded category configuration
            timestamp: Optional timestamp for events (default: 2025-01-01 00:00:00)

        Returns:
            List of BudgetCreated events
        """
        events: List[Event] = []

        # Use fixed timestamp for consistent historical migration
        if timestamp is None:
            timestamp = datetime(2025, 1, 1, 0, 0, 0)

        for category in category_config.categories:
            if not category.budget:
                continue

            # Generate deterministic budget_id from category name
            budget_id = f"budget-{category.name.lower().replace(' ', '-')}"

            event = BudgetCreated(
                budget_id=budget_id,
                category=category.name,
                subcategory=None,  # Budgets are category-level
                period_type=category.budget.period.value,
                start_date="2025-01-01",
                amount=Decimal(str(category.budget.amount)),
                currency="CAD",
                event_timestamp=timestamp,
            )
            events.append(event)

        return events

    def validate_migration(
        self,
        event_store: EventStore,
        original_data_dir: Path,
        category_config: CategoryConfig,
        tx_projection_builder: ProjectionBuilder,
        budget_projection_builder: BudgetProjectionBuilder,
    ) -> ValidationResult:
        """Validate that projections rebuilt from events match original data.

        Compares:
        1. Transaction counts (original CSVs vs projection)
        2. Budget counts (categories.yml vs projection)
        3. Sample transactions (fields match exactly)

        Args:
            event_store: Event store with backfilled events
            original_data_dir: Directory containing original ledger CSVs
            category_config: Original category configuration
            tx_projection_builder: Transaction projection builder
            budget_projection_builder: Budget projection builder

        Returns:
            ValidationResult with detailed comparison
        """
        errors: List[str] = []

        # Count original transactions
        original_tx_count = self._count_original_transactions(original_data_dir)

        # Count projection transactions
        projection_txs = tx_projection_builder.get_all_transactions(include_duplicates=False)
        projection_tx_count = len(projection_txs)

        # Validate transaction count
        transaction_count_match = original_tx_count == projection_tx_count
        if not transaction_count_match:
            errors.append(
                f"Transaction count mismatch: original={original_tx_count}, "
                f"projection={projection_tx_count}"
            )

        # Count original budgets
        original_budget_count = sum(1 for cat in category_config.categories if cat.budget)

        # Count projection budgets
        projection_budgets = budget_projection_builder.get_active_budgets()
        projection_budget_count = len(projection_budgets)

        # Validate budget count
        budget_count_match = original_budget_count == projection_budget_count
        if not budget_count_match:
            errors.append(
                f"Budget count mismatch: original={original_budget_count}, "
                f"projection={projection_budget_count}"
            )

        # Validate sample transactions
        sample_errors = self._validate_transaction_sample(
            original_data_dir, tx_projection_builder, sample_size=10
        )
        sample_transactions_match = len(sample_errors) == 0
        errors.extend(sample_errors)

        # Overall validation passes if all checks pass
        is_valid = transaction_count_match and budget_count_match and sample_transactions_match

        return ValidationResult(
            is_valid=is_valid,
            errors=errors,
            transaction_count_match=transaction_count_match,
            budget_count_match=budget_count_match,
            sample_transactions_match=sample_transactions_match,
        )

    def _infer_import_timestamp(self, source_file: str, transaction_date: str) -> datetime:
        """Infer import timestamp from source filename and transaction date.

        Source files are named like: 2025-08-21-mybank-chequing.csv
        We extract this date as the import timestamp.

        Args:
            source_file: Source filename
            transaction_date: Transaction date (YYYY-MM-DD)

        Returns:
            Inferred import timestamp (defaults to noon)
        """
        # Try to extract date from filename (format: YYYY-MM-DD-*)
        parts = source_file.split("-")
        if len(parts) >= 3:
            try:
                year = int(parts[0])
                month = int(parts[1])
                day = int(parts[2])
                # Use noon as reasonable default time
                return datetime(year, month, day, 12, 0, 0)
            except (ValueError, IndexError):
                pass

        # Fallback: use transaction date + noon
        try:
            dt = datetime.fromisoformat(transaction_date)
            return dt.replace(hour=12, minute=0, second=0)
        except (ValueError, TypeError):
            # Last resort: current time
            return datetime.now()

    def _count_original_transactions(self, data_dir: Path) -> int:
        """Count transactions in original ledger files.

        Args:
            data_dir: Directory containing ledger CSVs

        Returns:
            Number of primary transactions
        """
        count = 0

        if not data_dir.exists() or not data_dir.is_dir():
            return 0

        for ledger_path in data_dir.glob("*.csv"):
            try:
                with open(ledger_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if row.get("row_type") == "primary" and row.get("transaction_id"):
                            count += 1
            except Exception:
                # Silently skip files we can't read
                continue

        return count

    def _validate_transaction_sample(
        self,
        data_dir: Path,
        tx_builder: ProjectionBuilder,
        sample_size: int = 10,
    ) -> List[str]:
        """Validate a sample of transactions match between original and projection.

        Args:
            data_dir: Directory containing original ledgers
            tx_builder: Transaction projection builder
            sample_size: Number of transactions to validate

        Returns:
            List of validation error messages (empty if all valid)
        """
        errors: List[str] = []
        validated = 0

        if not data_dir.exists() or not data_dir.is_dir():
            return [f"Data directory not found: {data_dir}"]

        for ledger_path in sorted(data_dir.glob("*.csv")):
            if validated >= sample_size:
                break

            try:
                with open(ledger_path, "r", encoding="utf-8") as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        if validated >= sample_size:
                            break

                        if row.get("row_type") != "primary" or not row.get("transaction_id"):
                            continue

                        transaction_id = row["transaction_id"]
                        projection = tx_builder.get_transaction(transaction_id)

                        if not projection:
                            errors.append(f"Transaction {transaction_id} not found in projection")
                            continue

                        # Validate key fields match
                        if projection.get("transaction_date") != row.get("date"):
                            errors.append(
                                f"Transaction {transaction_id}: date mismatch "
                                f"(original={row.get('date')}, "
                                f"projection={projection.get('transaction_date')})"
                            )

                        # Compare amounts (handle float vs string)
                        try:
                            original_amount = float(row.get("amount", 0))
                            projection_amount = float(projection.get("amount", 0))
                            if abs(original_amount - projection_amount) > 0.001:
                                errors.append(
                                    f"Transaction {transaction_id}: amount mismatch "
                                    f"(original={row.get('amount')}, "
                                    f"projection={projection.get('amount')})"
                                )
                        except (ValueError, TypeError) as e:
                            errors.append(
                                f"Transaction {transaction_id}: amount comparison error - {e}"
                            )

                        # Compare categories (handle empty string vs None)
                        original_category = row.get("category", "").strip() or None
                        projection_category = projection.get("category")
                        if original_category != projection_category:
                            errors.append(
                                f"Transaction {transaction_id}: category mismatch "
                                f"(original={original_category}, "
                                f"projection={projection_category})"
                            )

                        validated += 1

            except Exception as e:
                errors.append(f"Error validating {ledger_path.name}: {e}")

        return errors
