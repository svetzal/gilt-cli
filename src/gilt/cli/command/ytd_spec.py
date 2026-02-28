from __future__ import annotations

"""Tests for ytd command --compare flag and service display."""

from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rich.console import Console

from gilt.cli.command.ytd import run
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.events import TransactionEnriched, TransactionImported
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _build_projections_with_enrichment(
    workspace: Workspace,
    groups: list[TransactionGroup],
    enrichments: list[TransactionEnriched] | None = None,
):
    """Build event store and projections, optionally with enrichment events."""
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

    for enrichment in enrichments or []:
        store.append_event(enrichment)

    builder = ProjectionBuilder(workspace.projections_path)
    builder.rebuild_from_scratch(store)


class DescribeYtdCompareFlag:
    """Tests for ytd --compare flag."""

    def it_should_show_only_enriched_transactions(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            Path(tmpdir, "data", "accounts").mkdir(parents=True)

            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="ACME CORP PAYMENT",
                        amount=-50.00,
                        currency="CAD",
                        account_id="TEST_ACCT",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="RAW BANK DESC",
                        amount=-100.00,
                        currency="CAD",
                        account_id="TEST_ACCT",
                    ),
                ),
            ]

            enrichments = [
                TransactionEnriched(
                    transaction_id="2222222222222222",
                    vendor="Sample Store Inc.",
                    enrichment_source="test.json",
                ),
            ]

            _build_projections_with_enrichment(workspace, groups, enrichments)

            rc = run(
                account="TEST_ACCT",
                year=2025,
                workspace=workspace,
                compare=True,
            )
            assert rc == 0

    def it_should_return_zero_when_no_enriched_transactions(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            Path(tmpdir, "data", "accounts").mkdir(parents=True)

            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="ACME CORP PAYMENT",
                        amount=-50.00,
                        currency="CAD",
                        account_id="TEST_ACCT",
                    ),
                ),
            ]

            _build_projections_with_enrichment(workspace, groups)

            rc = run(
                account="TEST_ACCT",
                year=2025,
                workspace=workspace,
                compare=True,
            )
            assert rc == 0

    def it_should_not_filter_transactions_without_compare_flag(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            Path(tmpdir, "data", "accounts").mkdir(parents=True)

            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="ACME CORP PAYMENT",
                        amount=-50.00,
                        currency="CAD",
                        account_id="TEST_ACCT",
                    ),
                ),
            ]

            _build_projections_with_enrichment(workspace, groups)

            # Without compare, all transactions should appear (normal behavior)
            rc = run(
                account="TEST_ACCT",
                year=2025,
                workspace=workspace,
            )
            assert rc == 0


class DescribeYtdServiceDisplay:
    """Tests for service field display in ytd command."""

    def it_should_show_vendor_dash_service_when_service_present(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            Path(tmpdir, "data", "accounts").mkdir(parents=True)

            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="APPLE.COM/BILL",
                        amount=-9.99,
                        currency="CAD",
                        account_id="TEST_ACCT",
                    ),
                ),
            ]

            enrichments = [
                TransactionEnriched(
                    transaction_id="1111111111111111",
                    vendor="Apple",
                    service="Max Shmexy",
                    enrichment_source="test.json",
                ),
            ]

            _build_projections_with_enrichment(workspace, groups, enrichments)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.ytd.console", test_console):
                rc = run(
                    account="TEST_ACCT",
                    year=2025,
                    workspace=workspace,
                )
            assert rc == 0
            output = buf.getvalue()
            assert "Apple - Max Shmexy" in output

    def it_should_show_only_vendor_when_service_is_null(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            Path(tmpdir, "data", "accounts").mkdir(parents=True)

            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="ACME CORP PAYMENT",
                        amount=-50.00,
                        currency="CAD",
                        account_id="TEST_ACCT",
                    ),
                ),
            ]

            enrichments = [
                TransactionEnriched(
                    transaction_id="1111111111111111",
                    vendor="Acme Corp",
                    enrichment_source="test.json",
                ),
            ]

            _build_projections_with_enrichment(workspace, groups, enrichments)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.ytd.console", test_console):
                rc = run(
                    account="TEST_ACCT",
                    year=2025,
                    workspace=workspace,
                )
            assert rc == 0
            output = buf.getvalue()
            assert "Acme Corp" in output
            assert "Acme Corp -" not in output

    def it_should_show_service_column_in_compare_mode(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            Path(tmpdir, "data", "accounts").mkdir(parents=True)

            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="APPLE.COM/BILL",
                        amount=-9.99,
                        currency="CAD",
                        account_id="TEST_ACCT",
                    ),
                ),
            ]

            enrichments = [
                TransactionEnriched(
                    transaction_id="1111111111111111",
                    vendor="Apple",
                    service="Max Shmexy",
                    enrichment_source="test.json",
                ),
            ]

            _build_projections_with_enrichment(workspace, groups, enrichments)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.ytd.console", test_console):
                rc = run(
                    account="TEST_ACCT",
                    year=2025,
                    workspace=workspace,
                    compare=True,
                )
            assert rc == 0
            output = buf.getvalue()
            assert "Service" in output
            assert "Max Shmexy" in output

    def it_should_show_raw_description_in_raw_mode_even_with_service(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            Path(tmpdir, "data", "accounts").mkdir(parents=True)

            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="APPLE.COM/BILL",
                        amount=-9.99,
                        currency="CAD",
                        account_id="TEST_ACCT",
                    ),
                ),
            ]

            enrichments = [
                TransactionEnriched(
                    transaction_id="1111111111111111",
                    vendor="Apple",
                    service="Max Shmexy",
                    enrichment_source="test.json",
                ),
            ]

            _build_projections_with_enrichment(workspace, groups, enrichments)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.ytd.console", test_console):
                rc = run(
                    account="TEST_ACCT",
                    year=2025,
                    workspace=workspace,
                    raw=True,
                )
            assert rc == 0
            output = buf.getvalue()
            assert "APPLE.COM/BILL" in output
            assert "Apple - Max Shmexy" not in output
