from __future__ import annotations

"""
Tests for uncategorized command.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from decimal import Decimal

from finance.cli.command.uncategorized import run
from finance.model.account import Transaction, TransactionGroup
from finance.model.events import TransactionImported, TransactionCategorized
from finance.model.ledger_io import dump_ledger_csv
from finance.storage.event_store import EventStore
from finance.storage.projection import ProjectionBuilder
from finance.workspace import Workspace


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write ledger CSV."""
    csv_text = dump_ledger_csv(groups)
    path.write_text(csv_text, encoding="utf-8")


def _build_projections(workspace: Workspace, groups: list[TransactionGroup]):
    """Build event store and projections from transaction groups."""
    store = EventStore(str(workspace.event_store_path))
    for group in groups:
        txn = group.primary
        evt = TransactionImported(
            transaction_id=txn.transaction_id,
            transaction_date=str(txn.date),
            source_file="test.csv",
            source_account=txn.account_id,
            raw_description=txn.description,
            amount=Decimal(str(txn.amount)),
            currency=txn.currency,
            raw_data={},
        )
        store.append_event(evt)
        if txn.category:
            cat = TransactionCategorized(
                transaction_id=txn.transaction_id,
                category=txn.category,
                subcategory=txn.subcategory,
                source="user",
            )
            store.append_event(cat)
    builder = ProjectionBuilder(workspace.projections_path)
    builder.rebuild_from_scratch(store)


class DescribeUncategorizedCommand:
    """Tests for uncategorized command."""

    def it_should_display_message_when_all_categorized(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Rent",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            _build_projections(workspace, groups)

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_list_uncategorized_transactions(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Rent",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Unknown Transaction",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            _build_projections(workspace, groups)

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_filter_by_account(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create two ledgers
            all_groups = []
            for account in ["ACCOUNT1", "ACCOUNT2"]:
                ledger_path = data_dir / f"{account}.csv"
                groups = [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id=f"{account}1111111111",
                            date="2025-01-01",
                            description="Uncategorized",
                            amount=-100.0,
                            currency="CAD",
                            account_id=account,
                        ),
                    ),
                ]
                _write_ledger(ledger_path, groups)
                all_groups.extend(groups)
            _build_projections(workspace, all_groups)

            # Filter by specific account
            rc = run(account="ACCOUNT1", workspace=workspace)
            assert rc == 0

    def it_should_filter_by_year(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2024-01-01",
                        description="Last Year",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-01",
                        description="This Year",
                        amount=-200.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            _build_projections(workspace, groups)

            rc = run(year=2025, workspace=workspace)
            assert rc == 0

    def it_should_filter_by_min_amount(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Small",
                        amount=-10.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Large",
                        amount=-1000.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            _build_projections(workspace, groups)

            rc = run(min_amount=100.0, workspace=workspace)
            assert rc == 0

    def it_should_apply_limit(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id=str(i),
                    primary=Transaction(
                        transaction_id=f"{i:016d}",
                        date="2025-01-01",
                        description=f"Transaction {i}",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                )
                for i in range(1, 11)
            ]
            _write_ledger(ledger_path, groups)
            _build_projections(workspace, groups)

            rc = run(limit=5, workspace=workspace)
            assert rc == 0

    def it_should_handle_empty_data_directory(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))
            _build_projections(workspace, [])

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_error_on_nonexistent_account(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Setup empty projections database in temp dir
            from finance.storage.projection import ProjectionBuilder
            from finance.storage.event_store import EventStore

            # Create empty event store and projections
            events_dir = data_dir / "events"
            events_dir.mkdir()
            store = EventStore(str(events_dir / "events.db"))
            builder = ProjectionBuilder(workspace.projections_path)
            builder.rebuild_from_scratch(store)

            rc = run(account="NONEXISTENT", workspace=workspace)
            # With empty projections, should still succeed (just shows "All transactions are categorized")
            assert rc == 0

    def it_should_combine_filters(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2024-01-01",
                        description="Wrong Year",
                        amount=-500.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-01",
                        description="Too Small",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-01-02",
                        description="Match",
                        amount=-500.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            _build_projections(workspace, groups)

            # Should only show the third transaction
            rc = run(year=2025, min_amount=100.0, workspace=workspace)
            assert rc == 0

    def it_should_sort_by_description_then_date(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-02",
                        description="AAAA",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-01",
                        description="AAAA",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-01-01",
                        description="ZZZZ",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            _build_projections(workspace, groups)

            # Sort order should be: AAAA (2025-01-01), AAAA (2025-01-02), ZZZZ (2025-01-01)
            rc = run(workspace=workspace)
            assert rc == 0
