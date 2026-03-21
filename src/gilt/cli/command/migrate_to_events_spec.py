from __future__ import annotations

"""
Specs for the migrate-to-events CLI command.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

import yaml

from gilt.cli.command.migrate_to_events import run
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig
from gilt.model.category_io import save_categories_config
from gilt.model.ledger_io import dump_ledger_csv
from gilt.storage.event_store import EventStore
from gilt.workspace import Workspace

# ---------------------------------------------------------------------------
# Setup helpers
# ---------------------------------------------------------------------------


def _write_synthetic_ledger(data_dir: Path, account_id: str = "MYBANK_CHQ") -> Path:
    """Write a minimal synthetic ledger CSV and return its path."""
    groups = [
        TransactionGroup(
            group_id="grp001",
            primary=Transaction(
                transaction_id="aaaa0001aaaa0001",
                date="2025-01-10",
                description="SAMPLE STORE",
                amount=-50.0,
                currency="CAD",
                account_id=account_id,
                category="Shopping",
            ),
        ),
        TransactionGroup(
            group_id="grp002",
            primary=Transaction(
                transaction_id="aaaa0002aaaa0002",
                date="2025-01-15",
                description="EXAMPLE UTILITY",
                amount=-150.0,
                currency="CAD",
                account_id=account_id,
                category="Housing",
            ),
        ),
    ]
    ledger_path = data_dir / f"{account_id}.csv"
    ledger_path.write_text(dump_ledger_csv(groups), encoding="utf-8")
    return ledger_path


def _write_synthetic_categories(cats_path: Path) -> None:
    """Write a minimal synthetic categories.yml."""
    config = CategoryConfig(
        categories=[
            Category(name="Shopping", budget=Budget(amount=300.0, period=BudgetPeriod.monthly)),
            Category(name="Housing", budget=Budget(amount=2000.0, period=BudgetPeriod.monthly)),
        ]
    )
    save_categories_config(cats_path, config)


def _write_accounts_yml(accounts_config_path: Path, account_id: str = "MYBANK_CHQ") -> None:
    """Write a minimal accounts.yml config."""
    data = {"accounts": [{"account_id": account_id}]}
    accounts_config_path.parent.mkdir(parents=True, exist_ok=True)
    accounts_config_path.write_text(yaml.safe_dump(data), encoding="utf-8")


# ---------------------------------------------------------------------------
# Precondition: no CSV files
# ---------------------------------------------------------------------------


class DescribeMigrateToEventsPreconditions:
    """Specs for precondition checks before migration."""

    def it_should_return_1_when_no_csv_files_in_data_dir(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            # No CSVs written

            result = run(workspace=ws, write=False)
            assert result == 1

    def it_should_return_1_even_in_dry_run_when_no_csv_files(self):
        """Preconditions are checked before dry-run logic executes."""
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)

            result = run(workspace=ws, write=False)
            assert result == 1

    def it_should_return_1_when_event_store_already_has_events_and_no_force(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            # Pre-populate event store with at least one event
            ws.event_store_path.parent.mkdir(parents=True, exist_ok=True)
            store = EventStore(str(ws.event_store_path))
            from decimal import Decimal

            from gilt.model.events import TransactionImported

            store.append_event(
                TransactionImported(
                    transaction_id="bbbb0001bbbb0001",
                    transaction_date="2025-01-01",
                    source_file="existing.csv",
                    source_account="MYBANK_CHQ",
                    raw_description="ACME CORP",
                    amount=Decimal("-10.00"),
                    currency="CAD",
                    raw_data={},
                )
            )

            # Without --force, should refuse to overwrite
            result = run(workspace=ws, write=True, force=False)
            assert result == 1


# ---------------------------------------------------------------------------
# Dry-run mode
# ---------------------------------------------------------------------------


class DescribeMigrateToEventsDryRun:
    """Specs for dry-run mode (write=False)."""

    def it_should_return_0_when_csv_files_exist_and_write_is_false(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            result = run(workspace=ws, write=False)
            assert result == 0

    def it_should_not_create_event_store_db_in_dry_run(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            run(workspace=ws, write=False)

            assert not ws.event_store_path.exists()

    def it_should_not_create_projections_db_in_dry_run(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            run(workspace=ws, write=False)

            assert not ws.projections_path.exists()


# ---------------------------------------------------------------------------
# Write mode
# ---------------------------------------------------------------------------


class DescribeMigrateToEventsWriteMode:
    """Specs for write mode (write=True)."""

    def it_should_return_0_and_create_event_store_when_csv_files_exist(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            result = run(workspace=ws, write=True)
            assert result == 0
            assert ws.event_store_path.exists()

    def it_should_create_projections_db_after_successful_migration(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            run(workspace=ws, write=True)

            assert ws.projections_path.exists()

    def it_should_backfill_events_matching_ledger_transactions(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            run(workspace=ws, write=True)

            store = EventStore(str(ws.event_store_path))
            event_count = store.get_latest_sequence_number()
            # 2 transactions → at least 2 events
            assert event_count >= 2

    def it_should_overwrite_existing_event_store_when_force_is_true(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)

            # First migration
            run(workspace=ws, write=True)

            # Second migration with --force should succeed
            result = run(workspace=ws, write=True, force=True)
            assert result == 0

    def it_should_succeed_with_categories_yml_present(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
            _write_synthetic_ledger(ws.ledger_data_dir)
            ws.categories_config.parent.mkdir(parents=True, exist_ok=True)
            _write_synthetic_categories(ws.categories_config)

            result = run(workspace=ws, write=True)
            assert result == 0
            assert ws.event_store_path.exists()
            assert ws.projections_path.exists()
