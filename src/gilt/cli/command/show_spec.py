from __future__ import annotations

"""Tests for the gilt show command."""

import json
from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rich.console import Console

from gilt.cli.command.show import run
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.events import TransactionEnriched, TransactionImported
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _build_projections(
    workspace: Workspace,
    groups: list[TransactionGroup],
    enrichments: list[TransactionEnriched] | None = None,
) -> None:
    """Build event store and projections from synthetic transaction groups."""
    store = EventStore(str(workspace.event_store_path))
    for group in groups:
        txn = group.primary
        store.append_event(
            TransactionImported(
                transaction_id=txn.transaction_id,
                transaction_date=str(txn.date),
                source_file="test.csv",
                source_account=txn.account_id,
                raw_description=txn.description,
                amount=Decimal(str(txn.amount)),
                currency=txn.currency or "CAD",
                raw_data={},
            )
        )
    for enrichment in enrichments or []:
        store.append_event(enrichment)

    builder = ProjectionBuilder(workspace.projections_path)
    builder.build_from_scratch(store)


class DescribeShowSingleMatch:
    """show command — single matching transaction."""

    def it_should_return_zero_and_display_all_fields(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11223344",
                        date="2025-03-15",
                        description="EXAMPLE UTILITY PAYMENT",
                        amount=-142.50,
                        currency="CAD",
                        account_id="MYBANK_CHQ",
                    ),
                )
            ]
            _build_projections(workspace, groups)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabbccdd", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            assert "aabbccdd11223344" in output
            assert "2025-03-15" in output
            assert "MYBANK_CHQ" in output
            assert "EXAMPLE UTILITY PAYMENT" in output
            assert "-142.50" in output
            assert "CAD" in output

    def it_should_display_placeholder_for_null_enrichment_fields(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11223344",
                        date="2025-03-15",
                        description="SAMPLE STORE PURCHASE",
                        amount=-55.00,
                        currency="CAD",
                        account_id="MYBANK_CC",
                    ),
                )
            ]
            _build_projections(workspace, groups)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabbccdd", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            # Null enrichment fields render as placeholder
            assert "—" in output

    def it_should_display_enrichment_fields_when_present(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11223344",
                        date="2025-04-01",
                        description="ACME CORP CHARGE",
                        amount=-29.99,
                        currency="CAD",
                        account_id="MYBANK_CC",
                    ),
                )
            ]
            enrichments = [
                TransactionEnriched(
                    transaction_id="aabbccdd11223344",
                    vendor="ACME Corp",
                    service="Widget Subscription",
                    enrichment_source="receipt.json",
                    source_email="receipts@example.com",
                )
            ]
            _build_projections(workspace, groups, enrichments)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabbccdd", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            assert "ACME Corp" in output
            assert "Widget Subscription" in output
            assert "receipt.json" in output
            assert "receipts@example.com" in output

    def it_should_display_description_history_as_bulleted_list(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            # Build projections manually with a multi-entry description_history
            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11223344",
                        date="2025-05-01",
                        description="CURRENT DESCRIPTION",
                        amount=-10.00,
                        currency="CAD",
                        account_id="MYBANK_CHQ",
                    ),
                )
            ]
            _build_projections(workspace, groups)

            # Directly patch the projection row to have multiple description_history entries
            import sqlite3

            conn = sqlite3.connect(workspace.projections_path)
            conn.execute(
                "UPDATE transaction_projections SET description_history = ? "
                "WHERE transaction_id = ?",
                (
                    json.dumps(["OLD DESCRIPTION", "CURRENT DESCRIPTION"]),
                    "aabbccdd11223344",
                ),
            )
            conn.commit()
            conn.close()

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabbccdd", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            assert "OLD DESCRIPTION" in output
            assert "CURRENT DESCRIPTION" in output
            # Bullet character or at least both descriptions visible
            assert "•" in output

    def it_should_display_placeholder_for_null_description_history(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11223344",
                        date="2025-05-01",
                        description="SINGLE DESCRIPTION",
                        amount=-10.00,
                        currency="CAD",
                        account_id="MYBANK_CHQ",
                    ),
                )
            ]
            _build_projections(workspace, groups)

            import sqlite3

            conn = sqlite3.connect(workspace.projections_path)
            conn.execute(
                "UPDATE transaction_projections SET description_history = NULL "
                "WHERE transaction_id = ?",
                ("aabbccdd11223344",),
            )
            conn.commit()
            conn.close()

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabbccdd", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            assert "—" in output


class DescribeShowAmbiguousPrefix:
    """show command — ambiguous prefix matches multiple transactions."""

    def it_should_return_nonzero_and_list_candidates(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            # Two transactions with the same 8-char prefix
            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11111111",
                        date="2025-01-10",
                        description="SAMPLE STORE A",
                        amount=-10.00,
                        currency="CAD",
                        account_id="MYBANK_CHQ",
                    ),
                ),
                TransactionGroup(
                    group_id="g2",
                    primary=Transaction(
                        transaction_id="aabbccdd22222222",
                        date="2025-01-11",
                        description="SAMPLE STORE B",
                        amount=-20.00,
                        currency="CAD",
                        account_id="MYBANK_CHQ",
                    ),
                ),
            ]
            _build_projections(workspace, groups)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabbccdd", workspace=workspace)

            output = buf.getvalue()
            assert rc == 2
            assert "Ambiguous" in output
            # Both transactions should appear in the candidate list
            assert "SAMPLE STORE A" in output
            assert "SAMPLE STORE B" in output


class DescribeShowNoMatch:
    """show command — no matching transaction."""

    def it_should_return_one_and_print_clear_error(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11223344",
                        date="2025-01-01",
                        description="SOME TRANSACTION",
                        amount=-5.00,
                        currency="CAD",
                        account_id="MYBANK_CHQ",
                    ),
                )
            ]
            _build_projections(workspace, groups)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="ffffffff", workspace=workspace)

            output = buf.getvalue()
            assert rc == 1
            assert "ffffffff" in output


class DescribeShowPrefixValidation:
    """show command — prefix length validation."""

    def it_should_return_two_when_prefix_too_short(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11223344",
                        date="2025-01-01",
                        description="SOME TRANSACTION",
                        amount=-5.00,
                        currency="CAD",
                        account_id="MYBANK_CHQ",
                    ),
                )
            ]
            _build_projections(workspace, groups)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabb", workspace=workspace)

            output = buf.getvalue()
            assert rc == 2
            assert "8" in output  # mentions minimum length

    def it_should_accept_full_16_char_transaction_id(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                TransactionGroup(
                    group_id="g1",
                    primary=Transaction(
                        transaction_id="aabbccdd11223344",
                        date="2025-06-01",
                        description="ACME CORP PURCHASE",
                        amount=-99.00,
                        currency="CAD",
                        account_id="MYBANK_CC",
                    ),
                )
            ]
            _build_projections(workspace, groups)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabbccdd11223344", workspace=workspace)

            assert rc == 0


class DescribeShowNoProjections:
    """show command — projections database missing."""

    def it_should_return_one_when_projections_db_missing(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            # No projections built — DB does not exist

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.show.console", test_console):
                rc = run(txid="aabbccdd", workspace=workspace)

            assert rc == 1
