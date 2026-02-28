"""Tests for mark_duplicate CLI command."""

from unittest.mock import patch

import pytest

from gilt.cli.command import mark_duplicate
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


class DescribeMarkDuplicate:
    """Tests for mark_duplicate command."""

    @pytest.fixture
    def mock_projections(self, tmp_path):
        """Create mock projections with sample transactions."""
        # Create data directory for workspace
        data_dir = tmp_path / "data"
        data_dir.mkdir(parents=True, exist_ok=True)

        # Create accounts directory (required by workspace)
        accounts_dir = data_dir / "accounts"
        accounts_dir.mkdir(parents=True, exist_ok=True)

        proj_path = data_dir / "projections.db"
        builder = ProjectionBuilder(proj_path)

        # Create sample transactions via mock
        from gilt.model.events import TransactionImported

        event_store = EventStore(str(data_dir / "events.db"))

        # Transaction 1
        event1 = TransactionImported(
            transaction_id="abc12345678901234567890123456789",
            transaction_date="2025-01-15",
            source_file="test1.csv",
            source_account="TEST_ACCT",
            raw_description="PAYMENT TO MERCHANT",
            amount=-100.00,
            currency="CAD",
            raw_data={"description": "PAYMENT TO MERCHANT", "amount": "-100.00"},
        )
        event_store.append_event(event1)

        # Transaction 2
        event2 = TransactionImported(
            transaction_id="def98765432109876543210987654321",
            transaction_date="2025-01-15",
            source_file="test2.csv",
            source_account="TEST_ACCT",
            raw_description="Payment to Merchant Inc",
            amount=-100.00,
            currency="CAD",
            raw_data={"description": "Payment to Merchant Inc", "amount": "-100.00"},
        )
        event_store.append_event(event2)

        # Transaction 3 (different account)
        event3 = TransactionImported(
            transaction_id="xyz11111111111111111111111111111",
            transaction_date="2025-01-15",
            source_file="test3.csv",
            source_account="OTHER_ACCT",
            raw_description="Some transaction",
            amount=-100.00,
            currency="CAD",
            raw_data={"description": "Some transaction", "amount": "-100.00"},
        )
        event_store.append_event(event3)

        # Build projections
        builder.rebuild_from_scratch(event_store)

        return proj_path, event_store

    def it_should_mark_duplicate_in_dry_run_mode(self, mock_projections, tmp_path, capsys):
        """Test dry-run mode shows preview without persisting."""
        proj_path, event_store = mock_projections
        workspace = Workspace(root=tmp_path)

        with patch("gilt.cli.command.mark_duplicate.Prompt.ask", return_value="1"):
            result = mark_duplicate.run(
                primary_txid="abc12345",
                duplicate_txid="def98765",
                workspace=workspace,
                write=False,
            )

        assert result == 0

        # No event should be emitted in dry-run
        events = event_store.get_events_by_type("DuplicateConfirmed")
        assert len(events) == 0

    def it_should_emit_duplicate_confirmed_event_with_write(self, mock_projections, tmp_path):
        """Test that --write emits DuplicateConfirmed event."""
        proj_path, event_store = mock_projections
        workspace = Workspace(root=tmp_path)

        with (
            patch("gilt.cli.command.mark_duplicate.Prompt.ask", return_value="1"),
            patch("gilt.cli.command.mark_duplicate.EventSourcingService") as mock_es,
        ):
            # Mock the event store append
            mock_es.return_value.event_store = event_store

            result = mark_duplicate.run(
                primary_txid="abc12345",
                duplicate_txid="def98765",
                workspace=workspace,
                write=True,
            )

        assert result == 0

        # Check event was emitted
        duplicate_events = event_store.get_events_by_type("DuplicateConfirmed")
        assert len(duplicate_events) == 1

        event = duplicate_events[0]
        assert event.primary_transaction_id == "abc12345678901234567890123456789"
        assert event.duplicate_transaction_id == "def98765432109876543210987654321"
        assert event.canonical_description == "PAYMENT TO MERCHANT"
        assert event.user_rationale == "Manual duplicate marking"
        assert event.llm_was_correct is False

    def it_should_use_description_from_choice(self, mock_projections, tmp_path):
        """Test that choosing description 2 uses duplicate's description."""
        proj_path, event_store = mock_projections
        workspace = Workspace(root=tmp_path)

        with (
            patch("gilt.cli.command.mark_duplicate.Prompt.ask", return_value="2"),
            patch("gilt.cli.command.mark_duplicate.EventSourcingService") as mock_es,
        ):
            mock_es.return_value.event_store = event_store

            result = mark_duplicate.run(
                primary_txid="abc12345",
                duplicate_txid="def98765",
                workspace=workspace,
                write=True,
                )

        assert result == 0

        duplicate_events = event_store.get_events_by_type("DuplicateConfirmed")
        event = duplicate_events[0]

        # Should use duplicate's description (choice 2)
        assert event.canonical_description == "Payment to Merchant Inc"

    def it_should_error_on_same_transaction_id(self, mock_projections, tmp_path):
        """Test error when primary and duplicate are the same."""
        proj_path, _ = mock_projections
        workspace = Workspace(root=tmp_path)

        result = mark_duplicate.run(
            primary_txid="abc12345",
            duplicate_txid="abc12345",
            workspace=workspace,
            write=False,
        )

        assert result == 1

    def it_should_error_on_transaction_not_found(self, mock_projections, tmp_path):
        """Test error when transaction doesn't exist."""
        proj_path, _ = mock_projections
        workspace = Workspace(root=tmp_path)

        result = mark_duplicate.run(
            primary_txid="abc12345",
            duplicate_txid="notfound",
            workspace=workspace,
            write=False,
        )

        assert result == 1

    def it_should_error_on_short_transaction_prefix(self, mock_projections, tmp_path):
        """Test error when transaction ID prefix is too short."""
        proj_path, _ = mock_projections
        workspace = Workspace(root=tmp_path)

        result = mark_duplicate.run(
            primary_txid="abc123",  # Only 6 chars
            duplicate_txid="def98765",
            workspace=workspace,
            write=False,
        )

        assert result == 1

    def it_should_error_when_primary_already_marked_duplicate(self, mock_projections, tmp_path):
        """Test error when primary is already a duplicate."""
        proj_path, event_store = mock_projections
        workspace = Workspace(root=tmp_path)

        # Mark abc as duplicate first
        with (
            patch("gilt.cli.command.mark_duplicate.Prompt.ask", return_value="1"),
            patch("gilt.cli.command.mark_duplicate.EventSourcingService") as mock_es,
        ):
            mock_es.return_value.event_store = event_store
            mark_duplicate.run(
                primary_txid="def98765",
                duplicate_txid="abc12345",
                workspace=workspace,
                write=True,
            )

        # Rebuild projections
        builder = ProjectionBuilder(proj_path)
        builder.rebuild_incremental(event_store)

        # Try to use abc as primary again (should fail)
        result = mark_duplicate.run(
            primary_txid="abc12345",
            duplicate_txid="xyz11111",
            workspace=workspace,
            write=False,
        )

        assert result == 1

    def it_should_support_8_char_prefix_lookup(self, mock_projections, tmp_path):
        """Test that 8-character prefix is sufficient for lookup."""
        proj_path, event_store = mock_projections
        workspace = Workspace(root=tmp_path)

        with (
            patch("gilt.cli.command.mark_duplicate.Prompt.ask", return_value="1"),
            patch("gilt.cli.command.mark_duplicate.EventSourcingService") as mock_es,
        ):
            mock_es.return_value.event_store = event_store

            result = mark_duplicate.run(
                primary_txid="abc12345",  # 8 chars
                duplicate_txid="def98765",  # 8 chars
                workspace=workspace,
                write=True,
                )

        assert result == 0

    def it_should_error_on_missing_projections(self, tmp_path):
        """Test error when projections database doesn't exist."""
        workspace = Workspace(root=tmp_path)

        result = mark_duplicate.run(
            primary_txid="abc12345",
            duplicate_txid="def98765",
            workspace=workspace,
            write=False,
        )

        assert result == 1
