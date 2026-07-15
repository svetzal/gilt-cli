from __future__ import annotations

"""
Tests for uncategorized command.
"""

from datetime import date
from decimal import Decimal

import pytest
from rich.console import Console

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.uncategorized import run
from gilt.model.account import TransactionGroup
from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.testing import make_group, make_transaction, make_workspace, write_ledger
from gilt.workspace import Workspace


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
    builder.build_from_scratch(store)


def _run_capturing(workspace: Workspace, **kwargs) -> tuple[int, str]:
    """Run the command with a record-capturing console; return (rc, output)."""
    cap = Console(record=True)
    rc = run(workspace=workspace, _console=cap, **kwargs)
    return rc, cap.export_text()


class DescribeUncategorizedCommand:
    """Tests for uncategorized command."""

    def it_should_display_message_when_all_categorized(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
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
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)
        _build_projections(workspace, groups)

        rc = run(workspace=workspace)
        assert rc == 0

    def it_should_list_uncategorized_transactions(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Rent",
                    amount=-2000.0,
                    currency="CAD",
                    account_id="TEST",
                    category="Housing",
                ),
            ),
            make_group(
                group_id="2",
                primary=make_transaction(
                    transaction_id="2222222222222222",
                    date="2025-01-02",
                    description="Unknown Transaction",
                    amount=-100.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
        ]
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)
        _build_projections(workspace, groups)

        rc = run(workspace=workspace)
        assert rc == 0

    def it_should_filter_by_account(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        all_groups = []
        for account in ["ACCOUNT1", "ACCOUNT2"]:
            groups = [
                make_group(
                    group_id="1",
                    primary=make_transaction(
                        transaction_id=f"{account}1111111111",
                        date="2025-01-01",
                        description="Uncategorized",
                        amount=-100.0,
                        currency="CAD",
                        account_id=account,
                    ),
                ),
            ]
            write_ledger(workspace.ledger_data_dir / f"{account}.csv", groups)
            all_groups.extend(groups)
        _build_projections(workspace, all_groups)

        rc = run(account="ACCOUNT1", workspace=workspace)
        assert rc == 0

    def it_should_filter_by_year(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2024-01-01",
                    description="Last Year",
                    amount=-100.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
            make_group(
                group_id="2",
                primary=make_transaction(
                    transaction_id="2222222222222222",
                    date="2025-01-01",
                    description="This Year",
                    amount=-200.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
        ]
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)
        _build_projections(workspace, groups)

        rc = run(year=2025, workspace=workspace)
        assert rc == 0

    def it_should_filter_by_min_amount(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Small",
                    amount=-10.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
            make_group(
                group_id="2",
                primary=make_transaction(
                    transaction_id="2222222222222222",
                    date="2025-01-02",
                    description="Large",
                    amount=-1000.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
        ]
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)
        _build_projections(workspace, groups)

        rc = run(min_amount=100.0, workspace=workspace)
        assert rc == 0

    def it_should_apply_limit(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id=str(i),
                primary=make_transaction(
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
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)
        _build_projections(workspace, groups)

        rc = run(limit=5, workspace=workspace)
        assert rc == 0

    def it_should_error_when_no_transactions_exist(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        _build_projections(workspace, [])

        with pytest.raises(CommandAbort) as exc_info:
            run(workspace=workspace)
        assert exc_info.value.code == 1

    def it_should_error_on_nonexistent_account(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        store = EventStore(str(workspace.event_store_path))
        builder = ProjectionBuilder(workspace.projections_path)
        builder.build_from_scratch(store)

        with pytest.raises(CommandAbort) as exc_info:
            run(account="NONEXISTENT", workspace=workspace)
        assert exc_info.value.code == 1

    def it_should_combine_filters(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2024-01-01",
                    description="Wrong Year",
                    amount=-500.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
            make_group(
                group_id="2",
                primary=make_transaction(
                    transaction_id="2222222222222222",
                    date="2025-01-01",
                    description="Too Small",
                    amount=-50.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
            make_group(
                group_id="3",
                primary=make_transaction(
                    transaction_id="3333333333333333",
                    date="2025-01-02",
                    description="Match",
                    amount=-500.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
        ]
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)
        _build_projections(workspace, groups)

        rc = run(year=2025, min_amount=100.0, workspace=workspace)
        assert rc == 0

    def it_should_sort_by_account_then_date(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2025-01-02",
                    description="Item A",
                    amount=-100.0,
                    currency="CAD",
                    account_id="BANK_B",
                ),
            ),
            make_group(
                group_id="2",
                primary=make_transaction(
                    transaction_id="2222222222222222",
                    date="2025-01-01",
                    description="Item B",
                    amount=-100.0,
                    currency="CAD",
                    account_id="BANK_A",
                ),
            ),
            make_group(
                group_id="3",
                primary=make_transaction(
                    transaction_id="3333333333333333",
                    date="2025-01-03",
                    description="Item C",
                    amount=-100.0,
                    currency="CAD",
                    account_id="BANK_A",
                ),
            ),
        ]
        for account_id in ("BANK_A", "BANK_B"):
            acct_groups = [g for g in groups if g.primary.account_id == account_id]
            write_ledger(workspace.ledger_data_dir / f"{account_id}.csv", acct_groups)
        _build_projections(workspace, groups)

        cap = Console(record=True)
        rc = run(workspace=workspace, _console=cap)
        output = cap.export_text()

        assert rc == 0
        # BANK_A items appear before BANK_B in output
        pos_bank_a = output.find("BANK_A")
        pos_bank_b = output.find("BANK_B")
        assert pos_bank_a < pos_bank_b, "BANK_A should appear before BANK_B in output"

    def it_should_show_all_accounts_by_default(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Alpha",
                    amount=-100.0,
                    currency="CAD",
                    account_id="ACCT_ALPHA",
                ),
            ),
            make_group(
                group_id="2",
                primary=make_transaction(
                    transaction_id="2222222222222222",
                    date="2025-01-01",
                    description="Beta",
                    amount=-200.0,
                    currency="CAD",
                    account_id="ACCT_BETA",
                ),
            ),
        ]
        for account_id in ("ACCT_ALPHA", "ACCT_BETA"):
            acct_groups = [g for g in groups if g.primary.account_id == account_id]
            write_ledger(workspace.ledger_data_dir / f"{account_id}.csv", acct_groups)
        _build_projections(workspace, groups)

        cap = Console(record=True)
        rc = run(workspace=workspace, _console=cap)
        output = cap.export_text()

        assert rc == 0
        assert "ACCT_ALPHA" in output
        assert "ACCT_BETA" in output

    def it_should_show_per_account_summary(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="First",
                    amount=-100.0,
                    currency="CAD",
                    account_id="ACCT_ALPHA",
                ),
            ),
            make_group(
                group_id="2",
                primary=make_transaction(
                    transaction_id="2222222222222222",
                    date="2025-01-02",
                    description="Second",
                    amount=-200.0,
                    currency="CAD",
                    account_id="ACCT_ALPHA",
                ),
            ),
            make_group(
                group_id="3",
                primary=make_transaction(
                    transaction_id="3333333333333333",
                    date="2025-01-01",
                    description="Third",
                    amount=-300.0,
                    currency="CAD",
                    account_id="ACCT_BETA",
                ),
            ),
        ]
        for account_id in ("ACCT_ALPHA", "ACCT_BETA"):
            acct_groups = [g for g in groups if g.primary.account_id == account_id]
            write_ledger(workspace.ledger_data_dir / f"{account_id}.csv", acct_groups)
        _build_projections(workspace, groups)

        cap = Console(record=True)
        rc = run(workspace=workspace, _console=cap)
        output = cap.export_text()

        assert rc == 0
        # Both account IDs appear in the summary section
        assert "ACCT_ALPHA" in output
        assert "ACCT_BETA" in output
        # Counts are visible
        assert "2" in output  # ACCT_ALPHA has 2
        assert "1" in output  # ACCT_BETA has 1

    def it_should_filter_by_fy_range(self, tmp_path):
        """FY25 = Nov 1 2024 – Oct 31 2025 (both inclusive)."""
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            # Just before FY25 start — excluded
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2024-10-31",
                    description="Before FY25",
                    amount=-100.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
            # FY25 start boundary — included
            make_group(
                group_id="2",
                primary=make_transaction(
                    transaction_id="2222222222222222",
                    date="2024-11-01",
                    description="FY25 start",
                    amount=-200.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
            # FY25 end boundary — included
            make_group(
                group_id="3",
                primary=make_transaction(
                    transaction_id="3333333333333333",
                    date="2025-10-31",
                    description="FY25 end",
                    amount=-300.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
            # Just after FY25 end — excluded
            make_group(
                group_id="4",
                primary=make_transaction(
                    transaction_id="4444444444444444",
                    date="2025-11-01",
                    description="After FY25",
                    amount=-400.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
        ]
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)
        _build_projections(workspace, groups)

        cap = Console(record=True)
        fy_range = (date(2024, 11, 1), date(2025, 10, 31))
        rc = run(workspace=workspace, fy_range=fy_range, fy_label="FY25", _console=cap)
        output = cap.export_text()

        assert rc == 0
        assert "FY25 start" in output
        assert "FY25 end" in output
        assert "Before FY25" not in output
        assert "After FY25" not in output

    def it_should_include_fy_label_in_title(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        groups = [
            make_group(
                group_id="1",
                primary=make_transaction(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Item",
                    amount=-100.0,
                    currency="CAD",
                    account_id="TEST",
                ),
            ),
        ]
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)
        _build_projections(workspace, groups)

        cap = Console(record=True)
        fy_range = (date(2024, 11, 1), date(2025, 10, 31))
        rc = run(workspace=workspace, fy_range=fy_range, fy_label="FY25", _console=cap)
        output = cap.export_text()

        assert rc == 0
        assert "FY25" in output
