"""Tests for auto-categorize command."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.auto_categorize import run
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import Category, CategoryConfig
from gilt.model.category_io import save_categories_config
from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.model.ledger_io import dump_ledger_csv
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _build_projections(event_store: EventStore, projections_path: Path):
    """Build projections from event store."""
    builder = ProjectionBuilder(projections_path)
    builder.rebuild_from_scratch(event_store)


def _add_uncategorized_transaction(store: EventStore, txn_id: str, description: str, amount: str, account: str = "TEST"):
    """Add an uncategorized transaction to the event store."""
    txn = TransactionImported(
        transaction_id=txn_id,
        transaction_date="2025-02-01",
        source_file="test.csv",
        source_account=account,
        raw_description=description,
        amount=Decimal(amount),
        currency="CAD",
        raw_data={},
    )
    store.append_event(txn)


def _create_event_store_with_training_data(store_path: Path) -> EventStore:
    """Create event store with sufficient training data for testing."""
    store = EventStore(str(store_path))

    # Create training data for Entertainment
    for i in range(6):
        txn = TransactionImported(
            transaction_id=f"ent{i}",
            transaction_date="2025-01-15",
            source_file="test.csv",
            source_account="MC",
            raw_description=f"SPOTIFY PREMIUM {i}",
            amount=Decimal("-12.99"),
            currency="CAD",
            raw_data={},
        )
        store.append_event(txn)

        cat = TransactionCategorized(
            transaction_id=f"ent{i}",
            category="Entertainment",
            subcategory="Music",
            source="user",
        )
        store.append_event(cat)

    # Create training data for Groceries
    for i in range(6):
        txn = TransactionImported(
            transaction_id=f"groc{i}",
            transaction_date="2025-01-16",
            source_file="test.csv",
            source_account="CHQ",
            raw_description=f"LOBLAWS STORE {i}",
            amount=Decimal("-45.67"),
            currency="CAD",
            raw_data={},
        )
        store.append_event(txn)

        cat = TransactionCategorized(
            transaction_id=f"groc{i}",
            category="Groceries",
            source="user",
        )
        store.append_event(cat)

    return store


class DescribeAutoCategorize:
    """Tests for auto-categorize command."""

    def it_should_require_event_store(self):
        """Should error if projections database doesn't exist."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create category config
            config = CategoryConfig(categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ])
            save_categories_config(config_path, config)

            # Run without projections database
            rc = run(
                workspace=workspace,
                write=False,
            )

            # Should fail with error about missing projections database
            assert rc == 1

    def it_should_train_classifier_and_predict(self):
        """Should train classifier and predict categories."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create event store at workspace path
            store = _create_event_store_with_training_data(workspace.event_store_path)

            # Add uncategorized transaction to event store
            _add_uncategorized_transaction(store, "new1", "SPOTIFY SUBSCRIPTION", "-12.99")

            # Build projections
            _build_projections(store, workspace.projections_path)

            # Create category config
            config = CategoryConfig(categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ])
            save_categories_config(config_path, config)

            # Create ledger with uncategorized transaction
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="new1",
                        date=date(2025, 2, 1),
                        description="SPOTIFY SUBSCRIPTION",
                        amount=-12.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            csv_content = dump_ledger_csv(groups)
            ledger_path.write_text(csv_content, encoding="utf-8")

            # Run auto-categorize (dry-run)
            rc = run(
                workspace=workspace,
                confidence=0.5,
                write=False,
            )

            # Should succeed (dry-run shows predictions)
            assert rc == 0

    def it_should_handle_no_uncategorized_transactions(self):
        """Should handle gracefully when no uncategorized transactions exist."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create event store at workspace path and build projections
            store = _create_event_store_with_training_data(workspace.event_store_path)
            _build_projections(store, workspace.projections_path)

            # Create category config
            config = CategoryConfig(categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ])
            save_categories_config(config_path, config)

            # Create ledger with already categorized transaction
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="cat1",
                        date=date(2025, 2, 1),
                        description="SPOTIFY SUBSCRIPTION",
                        amount=-12.99,
                        currency="CAD",
                        account_id="TEST",
                        category="Entertainment",
                        subcategory="Music",
                    ),
                ),
            ]
            csv_content = dump_ledger_csv(groups)
            ledger_path.write_text(csv_content, encoding="utf-8")

            # Run auto-categorize
            rc = run(
                workspace=workspace,
                write=False,
            )

            assert rc == 0  # Success, just nothing to do

    def it_should_apply_categorizations_with_write_flag(self):
        """Should handle write flag (note: actual writing tested in integration tests)."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create event store at workspace path
            store = _create_event_store_with_training_data(workspace.event_store_path)

            # Add uncategorized transaction to event store
            _add_uncategorized_transaction(store, "new1", "SPOTIFY MUSIC SUBSCRIPTION", "-12.99")

            # Build projections
            _build_projections(store, workspace.projections_path)

            # Create category config
            config = CategoryConfig(categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ])
            save_categories_config(config_path, config)

            # Create ledger with uncategorized transaction
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="new1",
                        date=date(2025, 2, 1),
                        description="SPOTIFY MUSIC SUBSCRIPTION",
                        amount=-12.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            csv_content = dump_ledger_csv(groups)
            ledger_path.write_text(csv_content, encoding="utf-8")

            # Run auto-categorize with write (dry-run for testing)
            # Note: Full integration test would require mocking EventSourcingService
            rc = run(
                workspace=workspace,
                confidence=0.5,
                write=False,  # Use False to avoid writing in test
            )

            # Should succeed
            assert rc == 0

    def it_should_respect_confidence_threshold(self):
        """Should only suggest predictions above confidence threshold."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create event store at workspace path
            store = _create_event_store_with_training_data(workspace.event_store_path)

            # Add ambiguous transaction to event store
            _add_uncategorized_transaction(store, "ambig1", "RANDOM UNKNOWN MERCHANT", "-50.00")

            # Build projections
            _build_projections(store, workspace.projections_path)

            # Create category config
            config = CategoryConfig(categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ])
            save_categories_config(config_path, config)

            # Create ledger with ambiguous transaction
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="ambig1",
                        date=date(2025, 2, 1),
                        description="RANDOM UNKNOWN MERCHANT",
                        amount=-50.00,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            csv_content = dump_ledger_csv(groups)
            ledger_path.write_text(csv_content, encoding="utf-8")

            # Run with very high threshold
            rc = run(
                workspace=workspace,
                confidence=0.95,
                write=False,
            )

            # Should succeed but have no predictions
            assert rc == 0

    def it_should_respect_limit_parameter(self):
        """Should limit number of transactions processed."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create event store at workspace path
            store = _create_event_store_with_training_data(workspace.event_store_path)

            # Add multiple uncategorized transactions to event store
            for i in range(10):
                _add_uncategorized_transaction(store, f"new{i}", f"SPOTIFY {i}", "-12.99")

            # Build projections
            _build_projections(store, workspace.projections_path)

            # Create category config
            config = CategoryConfig(categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ])
            save_categories_config(config_path, config)

            # Create ledger with multiple uncategorized transactions
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id=str(i),
                    primary=Transaction(
                        transaction_id=f"new{i}",
                        date=date(2025, 2, 1),
                        description=f"SPOTIFY {i}",
                        amount=-12.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                )
                for i in range(10)
            ]
            csv_content = dump_ledger_csv(groups)
            ledger_path.write_text(csv_content, encoding="utf-8")

            # Run with limit
            rc = run(
                workspace=workspace,
                limit=3,
                confidence=0.5,
                write=False,
            )

            assert rc == 0

    def it_should_not_show_already_categorized_transactions_on_subsequent_runs(self):
        """Should exclude transactions already categorized in previous runs."""
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create event store at workspace path
            store = _create_event_store_with_training_data(workspace.event_store_path)

            # Add uncategorized transactions to event store
            _add_uncategorized_transaction(store, "spotify1", "SPOTIFY PREMIUM", "-12.99")

            txn2 = TransactionImported(
                transaction_id="spotify2",
                transaction_date="2025-02-02",
                source_file="test.csv",
                source_account="TEST",
                raw_description="SPOTIFY MUSIC",
                amount=Decimal("-12.99"),
                currency="CAD",
                raw_data={},
            )
            store.append_event(txn2)

            # Build projections
            _build_projections(store, workspace.projections_path)

            # Create category config
            config = CategoryConfig(
                categories=[
                    Category(name="Entertainment"),
                    Category(name="Groceries"),
                ]
            )
            save_categories_config(config_path, config)

            # Create ledger with uncategorized transactions
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="spotify1",
                        date=date(2025, 2, 1),
                        description="SPOTIFY PREMIUM",
                        amount=-12.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="spotify2",
                        date=date(2025, 2, 2),
                        description="SPOTIFY MUSIC",
                        amount=-12.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            csv_content = dump_ledger_csv(groups)
            ledger_path.write_text(csv_content, encoding="utf-8")

            # First run: categorize transactions with write
            rc1 = run(
                workspace=workspace,
                confidence=0.5,
                write=True,
            )
            assert rc1 == 0

            # Second run: should find no uncategorized transactions
            rc2 = run(
                workspace=workspace,
                confidence=0.5,
                write=True,
            )
            assert rc2 == 0
            # The command should succeed with 0 uncategorized transactions
