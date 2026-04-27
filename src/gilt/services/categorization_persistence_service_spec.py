"""
Tests for CategorizationPersistenceService.

These tests verify that the persistence orchestration correctly:
- Emits events per update
- Groups updates by account and writes CSVs
- Rebuilds projections after updates
- Returns accurate counts
- Handles missing ledger files gracefully
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gilt.model.events import TransactionCategorized
from gilt.model.ledger_io import dump_ledger_csv
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_persistence_service import (
    CategorizationPersistenceService,
    CategorizationUpdate,
)
from gilt.testing.fixtures import make_group


class DescribeCategorizationPersistenceService:
    """Base fixtures for all tests."""

    @pytest.fixture
    def mock_event_store(self):
        store = MagicMock()
        store.append_event = MagicMock()
        return store

    @pytest.fixture
    def mock_projection_builder(self):
        builder = MagicMock()
        builder.rebuild_incremental = MagicMock(return_value=2)
        return builder

    @pytest.fixture
    def ledger_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "accounts"
        d.mkdir()
        return d

    @pytest.fixture
    def ledger_repo(self, ledger_dir):
        return LedgerRepository(ledger_dir)

    @pytest.fixture
    def service(self, mock_event_store, mock_projection_builder, ledger_repo):
        return CategorizationPersistenceService(
            event_store=mock_event_store,
            projection_builder=mock_projection_builder,
            ledger_repo=ledger_repo,
        )


class DescribePersistCategorizations(DescribeCategorizationPersistenceService):
    """Tests for persist_categorizations method."""

    def it_should_emit_categorization_events_for_each_update(
        self, service, mock_event_store, ledger_dir
    ):
        """Should emit one TransactionCategorized event per update."""
        group = make_group(transaction_id="abc123", account_id="MYBANK_CHQ")
        ledger_path = ledger_dir / "MYBANK_CHQ.csv"
        ledger_path.write_text(dump_ledger_csv([group]), encoding="utf-8")

        updates = [
            CategorizationUpdate(
                transaction_id="abc123",
                account_id="MYBANK_CHQ",
                category="Utilities",
                subcategory="Electric",
                source="rule",
                confidence=0.95,
            )
        ]

        service.persist_categorizations(updates)

        mock_event_store.append_event.assert_called_once()
        emitted = mock_event_store.append_event.call_args[0][0]
        assert isinstance(emitted, TransactionCategorized)
        assert emitted.transaction_id == "abc123"
        assert emitted.category == "Utilities"
        assert emitted.subcategory == "Electric"

    def it_should_update_csv_ledgers_grouped_by_account(self, service, ledger_dir):
        """Should update the CSV file for each affected account."""
        group_a = make_group(transaction_id="txn001", account_id="MYBANK_CHQ")
        group_b = make_group(transaction_id="txn002", account_id="MYBANK_CC")

        (ledger_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group_a]), encoding="utf-8")
        (ledger_dir / "MYBANK_CC.csv").write_text(dump_ledger_csv([group_b]), encoding="utf-8")

        updates = [
            CategorizationUpdate(
                transaction_id="txn001",
                account_id="MYBANK_CHQ",
                category="Groceries",
                subcategory=None,
                source="user",
                confidence=1.0,
            ),
            CategorizationUpdate(
                transaction_id="txn002",
                account_id="MYBANK_CC",
                category="Dining",
                subcategory=None,
                source="user",
                confidence=1.0,
            ),
        ]

        result = service.persist_categorizations(updates)

        assert set(result.accounts_written) == {"MYBANK_CHQ", "MYBANK_CC"}

    def it_should_rebuild_projections_after_updates(
        self, service, mock_projection_builder, mock_event_store, ledger_dir
    ):
        """Should call rebuild_incremental after writing all CSV updates."""
        group = make_group(transaction_id="txn001", account_id="MYBANK_CHQ")
        (ledger_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group]), encoding="utf-8")

        updates = [
            CategorizationUpdate(
                transaction_id="txn001",
                account_id="MYBANK_CHQ",
                category="Transport",
                subcategory=None,
                source="rule",
                confidence=0.9,
            )
        ]

        service.persist_categorizations(updates)

        mock_projection_builder.rebuild_incremental.assert_called_once_with(mock_event_store)

    def it_should_return_count_of_updated_transactions(self, service, ledger_dir):
        """Should return the number of transactions processed."""
        group_a = make_group(transaction_id="txn001", account_id="MYBANK_CHQ")
        group_b = make_group(transaction_id="txn002", account_id="MYBANK_CHQ")
        (ledger_dir / "MYBANK_CHQ.csv").write_text(
            dump_ledger_csv([group_a, group_b]), encoding="utf-8"
        )

        updates = [
            CategorizationUpdate(
                transaction_id="txn001",
                account_id="MYBANK_CHQ",
                category="Food",
                subcategory=None,
                source="user",
                confidence=1.0,
            ),
            CategorizationUpdate(
                transaction_id="txn002",
                account_id="MYBANK_CHQ",
                category="Food",
                subcategory=None,
                source="user",
                confidence=1.0,
            ),
        ]

        result = service.persist_categorizations(updates)

        assert result.transactions_updated == 2
        assert result.events_emitted == 2

    def it_should_handle_missing_ledger_files_gracefully(self, service, ledger_dir):
        """Should skip accounts whose ledger CSV does not exist without raising."""
        updates = [
            CategorizationUpdate(
                transaction_id="txn001",
                account_id="UNKNOWN_ACCT",
                category="Misc",
                subcategory=None,
                source="rule",
                confidence=0.8,
            )
        ]

        result = service.persist_categorizations(updates)

        assert result.transactions_updated == 1
        assert result.events_emitted == 1
        assert "UNKNOWN_ACCT" not in result.accounts_written


class DescribePersistCategoryRename(DescribeCategorizationPersistenceService):
    """Tests for persist_category_rename method."""

    def it_should_persist_category_rename_across_accounts(self, service, ledger_dir):
        """Should update all matched groups and emit events for each."""
        group_a = make_group(transaction_id="txn001", account_id="MYBANK_CHQ", category="OldName")
        group_b = make_group(transaction_id="txn002", account_id="MYBANK_CC", category="OldName")

        (ledger_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group_a]), encoding="utf-8")
        (ledger_dir / "MYBANK_CC.csv").write_text(dump_ledger_csv([group_b]), encoding="utf-8")

        matches = [
            ("MYBANK_CHQ", group_a),
            ("MYBANK_CC", group_b),
        ]

        result = service.persist_category_rename(
            matches=matches,
            to_category="NewName",
            to_subcategory=None,
        )

        assert result.transactions_updated == 2
        assert result.events_emitted == 2
        assert set(result.accounts_written) == {"MYBANK_CHQ", "MYBANK_CC"}


class DescribeWriteCategorizationsToCsv:
    """Tests for write_categorizations_to_csv standalone function."""

    def it_should_update_category_in_csv_for_each_update(self, tmp_path):
        from gilt.services.categorization_persistence_service import write_categorizations_to_csv

        ledger_dir = tmp_path / "accounts"
        ledger_dir.mkdir()
        group = make_group(transaction_id="txn001", account_id="MYBANK_CHQ")
        (ledger_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group]), encoding="utf-8")

        from gilt.model.ledger_io import load_ledger_csv

        updates = [
            CategorizationUpdate(
                transaction_id="txn001",
                account_id="MYBANK_CHQ",
                category="Groceries",
                subcategory="Fresh",
                source="user",
                confidence=1.0,
            )
        ]
        write_categorizations_to_csv(updates, LedgerRepository(ledger_dir))

        text = (ledger_dir / "MYBANK_CHQ.csv").read_text(encoding="utf-8")
        result = load_ledger_csv(text)
        assert result[0].primary.category == "Groceries"
        assert result[0].primary.subcategory == "Fresh"

    def it_should_skip_missing_ledger_files(self, tmp_path):
        from gilt.services.categorization_persistence_service import write_categorizations_to_csv

        ledger_dir = tmp_path / "accounts"
        ledger_dir.mkdir()

        updates = [
            CategorizationUpdate(
                transaction_id="txn001",
                account_id="MISSING_ACCT",
                category="Groceries",
                subcategory=None,
                source="user",
                confidence=1.0,
            )
        ]
        # Should not raise
        write_categorizations_to_csv(updates, LedgerRepository(ledger_dir))


class DescribeCategorizationUpdatesFromRuleMatches:
    def it_should_convert_rule_matches_to_categorization_updates(self):
        from gilt.services.categorization_persistence_service import (
            categorization_updates_from_rule_matches,
        )
        from gilt.services.rule_inference_service import InferredRule, RuleMatch

        rule = InferredRule(
            description="EXAMPLE UTILITY",
            category="Housing",
            subcategory="Utilities",
            evidence_count=10,
            total_count=10,
            confidence=0.95,
        )
        match = RuleMatch(
            transaction={
                "transaction_id": "abc12345",
                "account_id": "MYBANK_CHQ",
                "canonical_description": "EXAMPLE UTILITY",
                "amount": -50.0,
            },
            rule=rule,
        )

        updates = categorization_updates_from_rule_matches([match])

        assert len(updates) == 1
        assert updates[0].transaction_id == "abc12345"
        assert updates[0].account_id == "MYBANK_CHQ"
        assert updates[0].category == "Housing"
        assert updates[0].subcategory == "Utilities"
        assert updates[0].source == "rule"
        assert updates[0].confidence == 0.95

    def it_should_default_account_id_to_empty_string_when_missing(self):
        from gilt.services.categorization_persistence_service import (
            categorization_updates_from_rule_matches,
        )
        from gilt.services.rule_inference_service import InferredRule, RuleMatch

        rule = InferredRule(
            description="SAMPLE STORE",
            category="Shopping",
            subcategory=None,
            evidence_count=5,
            total_count=5,
            confidence=1.0,
        )
        match = RuleMatch(
            transaction={
                "transaction_id": "def67890",
                "canonical_description": "SAMPLE STORE",
                "amount": -25.0,
            },
            rule=rule,
        )

        updates = categorization_updates_from_rule_matches([match])
        assert updates[0].account_id == ""

    def it_should_return_empty_list_for_empty_input(self):
        from gilt.services.categorization_persistence_service import (
            categorization_updates_from_rule_matches,
        )

        assert categorization_updates_from_rule_matches([]) == []


class DescribePersistNoteUpdate:
    """Tests for persist_note_update standalone function."""

    def it_should_update_note_in_csv_file(self, tmp_path):
        from gilt.services.categorization_persistence_service import persist_note_update

        ledger_dir = tmp_path / "accounts"
        ledger_dir.mkdir()
        group = make_group(transaction_id="txn001", account_id="MYBANK_CHQ")
        (ledger_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group]), encoding="utf-8")

        persist_note_update(
            account_id="MYBANK_CHQ",
            transaction_id="txn001",
            note="paid by cash",
            ledger_repo=LedgerRepository(ledger_dir),
        )

        from gilt.model.ledger_io import load_ledger_csv

        text = (ledger_dir / "MYBANK_CHQ.csv").read_text(encoding="utf-8")
        result = load_ledger_csv(text)
        assert result[0].primary.notes == "paid by cash"

    def it_should_clear_note_when_none_passed(self, tmp_path):
        from gilt.services.categorization_persistence_service import persist_note_update

        ledger_dir = tmp_path / "accounts"
        ledger_dir.mkdir()
        group = make_group(transaction_id="txn001", account_id="MYBANK_CHQ")
        group.primary.notes = "old note"
        (ledger_dir / "MYBANK_CHQ.csv").write_text(dump_ledger_csv([group]), encoding="utf-8")

        persist_note_update(
            account_id="MYBANK_CHQ",
            transaction_id="txn001",
            note=None,
            ledger_repo=LedgerRepository(ledger_dir),
        )

        from gilt.model.ledger_io import load_ledger_csv

        text = (ledger_dir / "MYBANK_CHQ.csv").read_text(encoding="utf-8")
        result = load_ledger_csv(text)
        assert result[0].primary.notes is None

    def it_should_raise_when_ledger_file_not_found(self, tmp_path):
        import pytest

        from gilt.services.categorization_persistence_service import persist_note_update

        ledger_dir = tmp_path / "accounts"
        ledger_dir.mkdir()

        with pytest.raises(FileNotFoundError):
            persist_note_update(
                account_id="MISSING_ACCT",
                transaction_id="txn001",
                note="some note",
                ledger_repo=LedgerRepository(ledger_dir),
            )
