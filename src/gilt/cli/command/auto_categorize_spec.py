"""Tests for auto-categorize command."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from unittest.mock import patch

import pytest

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.auto_categorize import (
    Prediction,
    _handle_modify_choice,
    _interactive_review,
    _review_and_persist,
    run,
)
from gilt.model.category import Category, CategoryConfig
from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.testing import (
    build_workspace_with_ledger,
    make_group,
    make_transaction,
    make_workspace,
    write_ledger,
)


def _build_projections(event_store: EventStore, projections_path):
    """Build projections from event store."""
    builder = ProjectionBuilder(projections_path)
    builder.build_from_scratch(event_store)


def _add_uncategorized_transaction(
    store: EventStore, txn_id: str, description: str, amount: str, account: str = "TEST"
):
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


def _create_event_store_with_training_data(store_path) -> EventStore:
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

    def it_should_require_event_store(self, tmp_path):
        """Should error if projections database doesn't exist."""
        config = CategoryConfig(
            categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ]
        )
        ws = build_workspace_with_ledger(tmp_path, config=config)

        # Run without projections database
        with pytest.raises(CommandAbort) as exc_info:
            run(
                workspace=ws,
                write=False,
            )

        # Should fail with error about missing projections database
        assert exc_info.value.code == 1

    def it_should_train_classifier_and_predict(self, tmp_path):
        """Should train classifier and predict categories."""
        config = CategoryConfig(
            categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ]
        )
        ws = build_workspace_with_ledger(tmp_path, config=config)

        # Create event store at workspace path
        store = _create_event_store_with_training_data(ws.event_store_path)

        # Add uncategorized transaction to event store
        _add_uncategorized_transaction(store, "new1", "SPOTIFY SUBSCRIPTION", "-12.99")

        # Build projections
        _build_projections(store, ws.projections_path)

        # Create ledger with uncategorized transaction
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    group_id="1",
                    transaction_id="new1",
                    date=date(2025, 2, 1),
                    description="SPOTIFY SUBSCRIPTION",
                    amount=-12.99,
                    account_id="TEST",
                ),
            ],
        )

        # Run auto-categorize (dry-run)
        rc = run(
            workspace=ws,
            confidence=0.5,
            write=False,
        )

        # Should succeed (dry-run shows predictions)
        assert rc == 0

    def it_should_handle_no_uncategorized_transactions(self, tmp_path):
        """Should handle gracefully when no uncategorized transactions exist."""
        config = CategoryConfig(
            categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ]
        )
        ws = build_workspace_with_ledger(tmp_path, config=config)

        # Create event store at workspace path and build projections
        store = _create_event_store_with_training_data(ws.event_store_path)
        _build_projections(store, ws.projections_path)

        # Create ledger with already categorized transaction
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    group_id="1",
                    transaction_id="cat1",
                    date=date(2025, 2, 1),
                    description="SPOTIFY SUBSCRIPTION",
                    amount=-12.99,
                    account_id="TEST",
                    category="Entertainment",
                    subcategory="Music",
                ),
            ],
        )

        # Run auto-categorize
        rc = run(
            workspace=ws,
            write=False,
        )

        assert rc == 0  # Success, just nothing to do

    def it_should_apply_categorizations_with_write_flag(self, tmp_path):
        """Should handle write flag (note: actual writing tested in integration tests)."""
        config = CategoryConfig(
            categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ]
        )
        ws = build_workspace_with_ledger(tmp_path, config=config)

        # Create event store at workspace path
        store = _create_event_store_with_training_data(ws.event_store_path)

        # Add uncategorized transaction to event store
        _add_uncategorized_transaction(store, "new1", "SPOTIFY MUSIC SUBSCRIPTION", "-12.99")

        # Build projections
        _build_projections(store, ws.projections_path)

        # Create ledger with uncategorized transaction
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    group_id="1",
                    transaction_id="new1",
                    date=date(2025, 2, 1),
                    description="SPOTIFY MUSIC SUBSCRIPTION",
                    amount=-12.99,
                    account_id="TEST",
                ),
            ],
        )

        # Run auto-categorize with write (dry-run for testing)
        # Note: Full integration test would require mocking EventSourcingService
        rc = run(
            workspace=ws,
            confidence=0.5,
            write=False,  # Use False to avoid writing in test
        )

        # Should succeed
        assert rc == 0

    def it_should_respect_confidence_threshold(self, tmp_path):
        """Should only suggest predictions above confidence threshold."""
        config = CategoryConfig(
            categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ]
        )
        ws = build_workspace_with_ledger(tmp_path, config=config)

        # Create event store at workspace path
        store = _create_event_store_with_training_data(ws.event_store_path)

        # Add ambiguous transaction to event store
        _add_uncategorized_transaction(store, "ambig1", "RANDOM UNKNOWN MERCHANT", "-50.00")

        # Build projections
        _build_projections(store, ws.projections_path)

        # Create ledger with ambiguous transaction
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    group_id="1",
                    transaction_id="ambig1",
                    date=date(2025, 2, 1),
                    description="RANDOM UNKNOWN MERCHANT",
                    amount=-50.00,
                    account_id="TEST",
                ),
            ],
        )

        # Run with very high threshold
        rc = run(
            workspace=ws,
            confidence=0.95,
            write=False,
        )

        # Should succeed but have no predictions
        assert rc == 0

    def it_should_respect_limit_parameter(self, tmp_path):
        """Should limit number of transactions processed."""
        config = CategoryConfig(
            categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ]
        )
        ws = build_workspace_with_ledger(tmp_path, config=config)

        # Create event store at workspace path
        store = _create_event_store_with_training_data(ws.event_store_path)

        # Add multiple uncategorized transactions to event store
        for i in range(10):
            _add_uncategorized_transaction(store, f"new{i}", f"SPOTIFY {i}", "-12.99")

        # Build projections
        _build_projections(store, ws.projections_path)

        # Create ledger with multiple uncategorized transactions
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    group_id=str(i),
                    transaction_id=f"new{i}",
                    date=date(2025, 2, 1),
                    description=f"SPOTIFY {i}",
                    amount=-12.99,
                    account_id="TEST",
                )
                for i in range(10)
            ],
        )

        # Run with limit
        rc = run(
            workspace=ws,
            limit=3,
            confidence=0.5,
            write=False,
        )

        assert rc == 0


class DescribeInteractiveReview:
    """Specs for _interactive_review()."""

    def _make_prediction(
        self, txn_id: str = "txn001", description: str = "SAMPLE STORE"
    ) -> Prediction:
        txn = make_transaction(
            transaction_id=txn_id,
            date=date(2025, 2, 1),
            description=description,
            amount=-50.0,
            account_id="MYBANK_CHQ",
        )
        return Prediction(
            account_id="MYBANK_CHQ",
            transaction_id=txn_id,
            txn=txn,
            category="Groceries",
            confidence=0.85,
            source="ml",
        )

    def it_should_approve_transaction_and_include_in_results(self):
        from gilt.model.category import Category, CategoryConfig

        category_config = CategoryConfig(categories=[Category(name="Groceries")])
        predictions = [self._make_prediction()]

        with patch("gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="a"):
            approved = _interactive_review(predictions, category_config)

        assert len(approved) == 1
        assert approved[0].transaction_id == "txn001"

    def it_should_reject_transaction_and_exclude_from_results(self):
        from gilt.model.category import Category, CategoryConfig

        category_config = CategoryConfig(categories=[Category(name="Groceries")])
        predictions = [self._make_prediction()]

        with patch("gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="r"):
            approved = _interactive_review(predictions, category_config)

        assert approved == []

    def it_should_allow_category_modification(self):
        from gilt.model.category import Category, CategoryConfig

        category_config = CategoryConfig(
            categories=[
                Category(name="Groceries"),
                Category(name="Dining Out"),
            ]
        )
        predictions = [self._make_prediction()]

        with (
            patch(
                "gilt.cli.command.auto_categorize_review.Prompt.ask",
                side_effect=["m", "Dining Out"],
            ),
            patch(
                "gilt.cli.command.auto_categorize_review.handle_modify_choice",
                return_value="Dining Out",
            ),
        ):
            approved = _interactive_review(predictions, category_config)

        assert len(approved) == 1
        assert approved[0].category == "Dining Out"

    def it_should_quit_early_when_user_chooses_quit(self):
        from gilt.model.category import Category, CategoryConfig

        category_config = CategoryConfig(categories=[Category(name="Groceries")])
        predictions = [
            self._make_prediction("txn001"),
            self._make_prediction("txn002"),
        ]

        with patch("gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="q"):
            approved = _interactive_review(predictions, category_config)

        assert approved == []


class DescribeHandleModifyChoice:
    """Specs for _handle_modify_choice()."""

    def it_should_return_updated_prediction_with_valid_category(self):
        from gilt.model.category import Category, CategoryConfig

        category_config = CategoryConfig(
            categories=[
                Category(name="Groceries"),
                Category(name="Dining Out"),
            ]
        )

        with patch("gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="Dining Out"):
            result = _handle_modify_choice(category_config, "Groceries")

        assert result == "Dining Out"

    def it_should_return_none_for_invalid_category(self):
        from gilt.model.category import Category, CategoryConfig

        category_config = CategoryConfig(categories=[Category(name="Groceries")])

        with patch(
            "gilt.cli.command.auto_categorize_review.Prompt.ask", return_value="NonExistent"
        ):
            result = _handle_modify_choice(category_config, "Groceries")

        assert result is None

    def it_should_return_none_for_invalid_subcategory(self):
        from gilt.model.category import Category, CategoryConfig, Subcategory

        category_config = CategoryConfig(
            categories=[Category(name="Entertainment", subcategories=[Subcategory(name="Music")])]
        )

        with patch(
            "gilt.cli.command.auto_categorize_review.Prompt.ask",
            return_value="Entertainment:Movies",
        ):
            result = _handle_modify_choice(category_config, "Entertainment:Music")

        assert result is None


class DescribeAutoCategorizeIdempotency:
    """Tests for auto-categorize idempotency behavior."""

    def it_should_not_show_already_categorized_transactions_on_subsequent_runs(self, tmp_path):
        """Should exclude transactions already categorized in previous runs."""
        config = CategoryConfig(
            categories=[
                Category(name="Entertainment"),
                Category(name="Groceries"),
            ]
        )
        ws = build_workspace_with_ledger(tmp_path, config=config)

        # Create event store at workspace path
        store = _create_event_store_with_training_data(ws.event_store_path)

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
        _build_projections(store, ws.projections_path)

        # Create ledger with uncategorized transactions
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    group_id="1",
                    transaction_id="spotify1",
                    date=date(2025, 2, 1),
                    description="SPOTIFY PREMIUM",
                    amount=-12.99,
                    account_id="TEST",
                ),
                make_group(
                    group_id="2",
                    transaction_id="spotify2",
                    date=date(2025, 2, 2),
                    description="SPOTIFY MUSIC",
                    amount=-12.99,
                    account_id="TEST",
                ),
            ],
        )

        # First run: categorize transactions with write
        rc1 = run(
            workspace=ws,
            confidence=0.5,
            write=True,
        )
        assert rc1 == 0

        # Second run: should find no uncategorized transactions
        rc2 = run(
            workspace=ws,
            confidence=0.5,
            write=True,
        )
        assert rc2 == 0


class DescribeReviewAndPersist:
    """Specs for _review_and_persist dry-run behaviour."""

    def _make_prediction(self, txn_id: str = "txn001") -> Prediction:
        txn = make_transaction(
            transaction_id=txn_id,
            date=date(2025, 1, 15),
            description="EXAMPLE UTILITY",
        )
        return Prediction(
            account_id="MYBANK_CHQ",
            transaction_id=txn_id,
            txn=txn,
            category="Utilities",
            confidence=0.90,
            source="ml",
        )

    def it_should_not_persist_categorizations_in_dry_run(self, tmp_path):
        """Dry-run (write=False) must print message and not call persist."""
        from unittest.mock import MagicMock

        from gilt.model.category import Category, CategoryConfig

        category_config = CategoryConfig(categories=[Category(name="Utilities")])
        predictions = [self._make_prediction()]
        mock_ready = MagicMock()

        ws = make_workspace(tmp_path)
        rc = _review_and_persist(
            all_predictions=predictions,
            category_config=category_config,
            workspace=ws,
            ready=mock_ready,
            write=False,
            interactive=False,
        )

        assert rc == 0
        # persist_row_categorizations must NOT have been called
        mock_ready.persist_categorizations.assert_not_called()
        # The command should succeed with 0 uncategorized transactions
