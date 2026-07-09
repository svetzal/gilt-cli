"""
Backfill events from existing data for event sourcing migration.

This command generates historical events from:
1. Existing transaction ledgers (CSVs) → TransactionImported + TransactionCategorized
2. Budget definitions (categories.yml) → BudgetCreated

⚠️  For most users, use 'gilt migrate-to-events --write' instead.
This command is for advanced use cases and debugging.

Used for Phase 7 migration to event-sourced architecture.

This is the imperative shell - handles I/O, display, and user interaction.
All business logic is in EventMigrationService.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gilt.model.category_io import load_categories_config
from gilt.services.event_migration_service import EventMigrationService, MigrationStats
from gilt.storage.budget_projection import BudgetProjectionBuilder
from gilt.workspace import Workspace

from ..console import print_dry_run_message, print_error
from ..event_sourcing_bootstrap import build_effective_paths, build_event_sourcing_service
from .backfill_events_view import (
    backfill_transactions_with_progress,
    display_budgets,
    display_projection_rebuild,
    display_summary,
    display_validation_checks,
    print_all_validations_passed,
    print_budget_step,
    print_migration_header,
    print_no_ledgers,
    print_transaction_step,
    print_validation_errors,
)


def _init_event_sourcing(
    workspace: Workspace,
    event_store_path: Path,
    projections_path: Path,
) -> tuple:
    """Initialize event sourcing service and return (es_service, service, event_store)."""
    es_service = build_event_sourcing_service(workspace, event_store_path, projections_path)
    service = EventMigrationService()
    event_store = es_service.get_event_store()
    return es_service, service, event_store


def run(
    *,
    workspace: Workspace,
    event_store_path: Path | None = None,
    projections_db_path: Path | None = None,
    budget_projections_db_path: Path | None = None,
    dry_run: bool = True,
) -> int:
    """Backfill events from existing ledgers and configuration.

    ⚠️  Most users should use 'gilt migrate-to-events --write' instead.

    Generates historical events from:
    - Transaction ledgers in data_dir
    - Budget definitions in categories_config

    Args:
        workspace: Workspace for resolving data paths
        event_store_path: Override path to event store database
        projections_db_path: Override path to transaction projections database
        budget_projections_db_path: Override path to budget projections database
        dry_run: If True, show what would be created without writing

    Returns:
        Exit code (0 = success)
    """
    data_dir = workspace.ledger_data_dir
    categories_config = workspace.categories_config
    (
        effective_event_store_path,
        effective_projections_db_path,
        effective_budget_projections_db_path,
    ) = build_effective_paths(
        workspace, event_store_path, projections_db_path, budget_projections_db_path
    )

    print_migration_header()

    if dry_run:
        print_dry_run_message()

    _, service, event_store = _init_event_sourcing(
        workspace, effective_event_store_path, effective_projections_db_path
    )
    return _run_backfill(
        data_dir,
        categories_config,
        event_store,
        service,
        dry_run,
        effective_event_store_path,
        effective_projections_db_path,
        effective_budget_projections_db_path,
    )


def _run_backfill(
    data_dir: Path,
    categories_config: Path,
    event_store,
    service: EventMigrationService,
    dry_run: bool,
    effective_event_store_path: Path,
    effective_projections_db_path: Path,
    effective_budget_projections_db_path: Path,
) -> int:
    """Backfill transactions and budgets, display summary, and validate if writing."""
    stats = MigrationStats(
        transaction_imported=0,
        transaction_categorized=0,
        budget_created=0,
        errors=0,
    )

    print_transaction_step()
    ledger_count = backfill_transactions_with_progress(data_dir, event_store, service, stats, dry_run)
    if ledger_count == 0:
        print_no_ledgers()

    print_budget_step()
    budget_lines = _backfill_budgets(categories_config, event_store, service, stats, dry_run)
    display_budgets(budget_lines, stats.budget_created)

    display_summary(stats, dry_run, effective_event_store_path)

    if not dry_run:
        return _validate_and_report(
            data_dir,
            categories_config,
            event_store,
            service,
            effective_projections_db_path,
            effective_budget_projections_db_path,
        )

    return 0


def _validate_and_report(
    data_dir: Path,
    categories_config: Path,
    event_store,
    service: EventMigrationService,
    projections_db_path: Path,
    budget_projections_db_path: Path,
) -> int:
    """Rebuild projections, run validation checks, and report results. Returns exit code."""
    validation_result = _validate_projections(
        data_dir,
        categories_config,
        event_store,
        service,
        projections_db_path,
        budget_projections_db_path,
    )
    display_projection_rebuild(validation_result.tx_count, validation_result.budget_count)

    if not validation_result.passed:
        print_error("✗ Validation failed")
        return 1

    if validation_result.validation:
        display_validation_checks(validation_result.validation)
        if validation_result.validation.errors:
            print_validation_errors(validation_result.validation.errors)
            return 1

    print_all_validations_passed()
    return 0


def _backfill_budgets(
    categories_config: Path,
    event_store,
    service: EventMigrationService,
    stats: MigrationStats,
    dry_run: bool,
) -> list[str]:
    """Backfill budget events from categories.yml. Returns display lines for each budget processed."""
    try:
        config = load_categories_config(categories_config)
    except (OSError, ValueError) as e:
        print_error(f"Error loading categories config: {e}")
        stats.errors += 1
        return []

    events = service.build_budget_events(config)
    display_lines: list[str] = []

    for event in events:
        from gilt.model.events import BudgetCreated

        if isinstance(event, BudgetCreated):
            category = config.find_category(event.category)
            if category and category.budget:
                display_lines.append(
                    f"  {category.name}: ${category.budget.amount}/{category.budget.period.value}"
                )

        stats.budget_created += 1

        if not dry_run:
            event_store.append_event(event)

    return display_lines


@dataclass
class _ValidationResult:
    passed: bool
    tx_count: int
    budget_count: int
    validation: object | None = None


def _validate_projections(
    data_dir: Path,
    categories_config: Path,
    event_store,
    service: EventMigrationService,
    projections_db_path: Path,
    budget_projections_db_path: Path,
) -> _ValidationResult:
    """Rebuild projections and validate against original data. Returns structured result."""
    from gilt.storage.projection import ProjectionBuilder

    tx_builder = ProjectionBuilder(projections_db_path)
    tx_count = tx_builder.build_from_scratch(event_store)

    budget_builder = BudgetProjectionBuilder(budget_projections_db_path)
    budget_count = budget_builder.build_from_scratch(event_store)

    try:
        config = load_categories_config(categories_config)
    except (OSError, ValueError) as e:
        print_error(f"Error loading categories config: {e}")
        return _ValidationResult(passed=False, tx_count=tx_count, budget_count=budget_count)

    from gilt.model.ledger_repository import LedgerRepository

    ledger_texts = LedgerRepository(data_dir).load_all_raw_texts()
    result = service.validate_migration(
        event_store, ledger_texts, config, tx_builder, budget_builder
    )

    passed = not result.errors
    return _ValidationResult(
        passed=passed, tx_count=tx_count, budget_count=budget_count, validation=result
    )
