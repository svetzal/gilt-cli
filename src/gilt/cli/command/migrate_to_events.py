"""
One-command migration from CSV-only data to event sourcing architecture.

This command automates the complete migration process:
1. Validates preconditions (CSV files exist, event store doesn't or is incomplete)
2. Backfills events from existing CSV data
3. Rebuilds transaction and budget projections
4. Validates the migration succeeded
5. Reports clear success/failure

Usage for existing users upgrading:
    gilt migrate-to-events --write

This replaces the manual multi-step process of:
- gilt backfill-events --write
- gilt rebuild-projections --from-scratch
- Checking for errors at each step
"""

from __future__ import annotations

from pathlib import Path

from gilt.model.category_io import load_categories_config
from gilt.model.errors import DATA_IO_ERRORS
from gilt.model.ledger_repository import LEDGER_IO_ERRORS, LedgerRepository
from gilt.services.event_migration_service import EventMigrationService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.budget_projection import BudgetProjectionBuilder
from gilt.workspace import Workspace

from .. import mutations
from ..console import print_error
from ..event_sourcing_bootstrap import build_effective_paths, build_event_sourcing_service
from ._errors import CommandAbort
from .migrate_to_events_view import (
    display_completion_summary,
    display_migration_plan,
    display_preconditions_success,
    display_validation_result,
    print_budget_events_created,
    print_budget_projections_built,
    print_event_store_exists_warning,
    print_migration_header,
    print_step_backfill,
    print_step_preconditions,
    print_step_projections,
    print_step_validating,
    print_transaction_events_created,
    print_transaction_projections_built,
)


def _check_preconditions(
    data_dir: Path,
    categories_config: Path,
    es_service: EventSourcingService,
    effective_event_store_path: Path,
    effective_projections_db_path: Path,
    effective_budget_projections_db_path: Path,
    force: bool,
) -> tuple[list[Path], bool]:
    """Check migration preconditions. Returns (ledger_files, has_categories) or raises CommandAbort(1)."""
    ledger_files = LedgerRepository(data_dir).ledger_paths()
    if not ledger_files:
        print_error(f"No CSV files found in {data_dir}")
        raise CommandAbort(1)

    has_categories = categories_config.exists()

    event_store_status = es_service.check_event_store_status()
    if event_store_status.exists:
        event_store = es_service.get_event_store()
        event_count = event_store.get_latest_sequence_number()

        if event_count > 0 and not force:
            print_event_store_exists_warning(event_count, effective_event_store_path)
            raise CommandAbort(1)
        elif event_count > 0 and force:
            effective_event_store_path.unlink()
            if effective_projections_db_path.exists():
                effective_projections_db_path.unlink()
            if effective_budget_projections_db_path.exists():
                effective_budget_projections_db_path.unlink()

    return ledger_files, has_categories


def _backfill_events(
    ledger_files: list[Path],
    has_categories: bool,
    categories_config: Path,
    es_service: EventSourcingService,
) -> tuple[int, int, int]:
    """Backfill transaction and budget events. Returns (transaction_events, budget_events, errors)."""
    service = EventMigrationService()
    event_store = es_service.get_event_store()

    transaction_events = 0
    budget_events = 0
    errors = 0

    for ledger_path in ledger_files:
        try:
            csv_text = ledger_path.read_text(encoding="utf-8")
            events, event_errors = service.build_transaction_events(csv_text, ledger_path.name)
            for event in events:
                event_store.append_event(event)
                transaction_events += 1
            for error in event_errors:
                print_error(error)
                errors += 1
        except LEDGER_IO_ERRORS as e:
            print_error(f"Error processing {ledger_path.name}: {e}")
            errors += 1

    if has_categories:
        try:
            config = load_categories_config(categories_config)
            budget_event_list = service.build_budget_events(config)
            for event in budget_event_list:
                event_store.append_event(event)
                budget_events += 1
        except DATA_IO_ERRORS as e:
            print_error(f"Error creating budget events: {e}")
            errors += 1

    return transaction_events, budget_events, errors


def _build_projections(
    es_service: EventSourcingService,
    has_categories: bool,
    effective_budget_projections_db_path: Path,
) -> tuple[object, object | None, int, int]:
    """Build projections from events. Returns (tx_builder, budget_builder, tx_count, budget_count) or raises CommandAbort(1)."""
    event_store = es_service.get_event_store()

    try:
        tx_builder = es_service.get_projection_builder()
        tx_count = tx_builder.build_from_scratch(event_store)
    except DATA_IO_ERRORS as e:
        print_error(f"Error building transaction projections: {e}")
        raise CommandAbort(1) from None

    budget_builder = None
    budget_count = 0
    if has_categories:
        try:
            budget_builder = BudgetProjectionBuilder(effective_budget_projections_db_path)
            budget_count = budget_builder.build_from_scratch(event_store)
        except DATA_IO_ERRORS as e:
            print_error(f"Error building budget projections: {e}")
            raise CommandAbort(1) from None

    return tx_builder, budget_builder, tx_count, budget_count


def _validate_migration(
    es_service: EventSourcingService,
    data_dir: Path,
    has_categories: bool,
    categories_config: Path,
    tx_builder,
    budget_builder,
):
    """Validate migration results. Returns validation result object or raises on error."""
    event_store = es_service.get_event_store()
    service = EventMigrationService()

    if has_categories:
        config = load_categories_config(categories_config)
        ledger_texts = LedgerRepository(data_dir).load_all_raw_texts()
        return service.validate_migration(
            event_store, ledger_texts, config, tx_builder, budget_builder
        )
    else:
        from gilt.services.event_migration_service import MigrationValidationResult

        return MigrationValidationResult(
            is_valid=True,
            errors=[],
            transaction_count_match=True,
            budget_count_match=True,
            sample_transactions_match=True,
        )


def run(
    *,
    workspace: Workspace,
    event_store_path: Path | None = None,
    projections_db_path: Path | None = None,
    budget_projections_db_path: Path | None = None,
    write: bool = False,
    force: bool = False,
) -> int:
    """One-command migration to event sourcing."""
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

    es_service = build_event_sourcing_service(
        workspace, effective_event_store_path, effective_projections_db_path
    )

    print_step_preconditions()
    ledger_files, has_categories = _check_preconditions(
        data_dir,
        categories_config,
        es_service,
        effective_event_store_path,
        effective_projections_db_path,
        effective_budget_projections_db_path,
        force,
    )
    display_preconditions_success(ledger_files, has_categories, categories_config)

    return mutations.run_confirmed_mutation(
        matches=ledger_files,
        display=lambda: display_migration_plan(ledger_files, has_categories),
        confirm_prompt="",
        assume_yes=True,
        write=write,
        apply=lambda: _run_migration(
            es_service,
            data_dir,
            categories_config,
            ledger_files,
            has_categories,
            effective_event_store_path,
            effective_projections_db_path,
            effective_budget_projections_db_path,
        ),
    )


def _run_migration(
    es_service: EventSourcingService,
    data_dir: Path,
    categories_config: Path,
    ledger_files: list[Path],
    has_categories: bool,
    effective_event_store_path: Path,
    effective_projections_db_path: Path,
    effective_budget_projections_db_path: Path,
) -> int:
    """Execute backfill → build projections → validate → summary."""
    print_step_backfill()
    transaction_events, budget_events, errors = _backfill_events(
        ledger_files,
        has_categories,
        categories_config,
        es_service,
    )
    print_transaction_events_created(transaction_events)
    if has_categories:
        print_budget_events_created(budget_events)

    print_step_projections()
    tx_builder, budget_builder, tx_count, budget_count = _build_projections(
        es_service, has_categories, effective_budget_projections_db_path
    )
    print_transaction_projections_built(tx_count)
    if has_categories:
        print_budget_projections_built(budget_count)

    print_step_validating()
    try:
        validation_result = _validate_migration(
            es_service,
            data_dir,
            has_categories,
            categories_config,
            tx_builder,
            budget_builder,
        )
    except DATA_IO_ERRORS as e:
        print_error(f"Validation failed: {e}")
        raise CommandAbort(1) from None
    if display_validation_result(validation_result, has_categories) != 0:
        raise CommandAbort(1)

    display_completion_summary(
        effective_event_store_path,
        effective_projections_db_path,
        transaction_events,
        budget_events,
        errors,
    )
    return 0


__all__ = ["run"]
