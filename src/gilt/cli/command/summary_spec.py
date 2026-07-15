from __future__ import annotations

"""
Tests for the summary command.
"""

from datetime import date
from decimal import Decimal

import pytest
from rich.console import Console

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.summary import run
from gilt.model.account import TransactionGroup
from gilt.model.events import TransactionCategorized, TransactionImported
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.testing import make_group, make_transaction
from gilt.workspace import Workspace


def _build_projections(workspace: Workspace, groups: list[TransactionGroup]) -> None:
    """Populate event store and build projections from transaction groups."""
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
    """Run summary command with a recording console; return (rc, output)."""
    cap = Console(record=True)
    rc = run(workspace=workspace, _console=cap, **kwargs)
    return rc, cap.export_text()


def _make_group(
    group_id: str,
    txn_id: str,
    amount: float,
    account_id: str = "MYBANK_CHQ",
    category: str | None = None,
    subcategory: str | None = None,
    txn_date: str = "2026-03-01",
    description: str = "SAMPLE STORE",
) -> TransactionGroup:
    return make_group(
        group_id=group_id,
        primary=make_transaction(
            transaction_id=txn_id,
            date=date.fromisoformat(txn_date),
            description=description,
            amount=amount,
            currency="CAD",
            account_id=account_id,
            category=category,
            subcategory=subcategory,
        ),
    )


class DescribeSummaryCommand:
    def it_should_return_error_when_projections_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        with pytest.raises(CommandAbort) as exc_info:
            _run_capturing(workspace)
        assert exc_info.value.code == 1

    def it_should_show_category_table_with_defaults(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -1000.0, category="Housing"),
            _make_group("2", "2222222222222222", -200.0, category="Food"),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, year=2026)
        assert rc == 0
        assert "Housing" in output
        assert "Food" in output

    def it_should_sort_by_abs_net_descending(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -100.0, category="Food"),
            _make_group("2", "2222222222222222", -1000.0, category="Housing"),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, year=2026)
        assert rc == 0
        # Housing (larger absolute) must appear before Food
        assert output.index("Housing") < output.index("Food")

    def it_should_filter_by_account(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group(
                "1",
                "1111111111111111",
                -500.0,
                account_id="MYBANK_CHQ",
                category="Housing",
            ),
            _make_group(
                "2",
                "2222222222222222",
                -100.0,
                account_id="MYBANK_CC",
                category="Food",
            ),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, account="MYBANK_CHQ", year=2026)
        assert rc == 0
        assert "Housing" in output
        assert "Food" not in output

    def it_should_filter_by_year(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -500.0, category="Housing", txn_date="2025-06-01"),
            _make_group("2", "2222222222222222", -200.0, category="Food", txn_date="2026-03-01"),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, year=2026)
        assert rc == 0
        assert "Food" in output
        assert "Housing" not in output

    def it_should_filter_by_fy_range(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -500.0, category="Housing", txn_date="2025-06-01"),
            _make_group("2", "2222222222222222", -200.0, category="Food", txn_date="2024-10-01"),
        ]
        _build_projections(workspace, groups)
        fy_range = (date(2024, 11, 1), date(2025, 10, 31))
        rc, output = _run_capturing(workspace, fy_range=fy_range, fy_label="FY25")
        assert rc == 0
        assert "Housing" in output
        assert "Food" not in output

    def it_should_include_fy_label_in_title(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -500.0, category="Housing", txn_date="2025-06-01"),
        ]
        _build_projections(workspace, groups)
        fy_range = (date(2024, 11, 1), date(2025, 10, 31))
        rc, output = _run_capturing(workspace, fy_range=fy_range, fy_label="FY25")
        assert rc == 0
        assert "FY25" in output

    def it_should_exclude_uncategorized_by_default(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -500.0, category="Housing"),
            _make_group("2", "2222222222222222", -200.0, category=None),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, year=2026)
        assert rc == 0
        assert "Housing" in output
        assert "uncategorized" not in output.lower()

    def it_should_include_uncategorized_when_flag_set(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -500.0, category="Housing"),
            _make_group("2", "2222222222222222", -200.0, category=None),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, year=2026, include_uncategorized=True)
        assert rc == 0
        assert "uncategorized" in output.lower()

    def it_should_show_subcategory_table_when_category_given(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -800.0, category="Housing", subcategory="Rent"),
            _make_group(
                "2", "2222222222222222", -200.0, category="Housing", subcategory="Utilities"
            ),
            _make_group("3", "3333333333333333", -100.0, category="Food"),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, category="Housing", year=2026)
        assert rc == 0
        assert "Rent" in output
        assert "Utilities" in output
        # Food should not appear — it's a different category
        assert "Food" not in output

    def it_should_show_dash_for_none_subcategory(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -500.0, category="Housing", subcategory=None),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, category="Housing", year=2026)
        assert rc == 0
        assert "—" in output  # em-dash

    def it_should_show_pct_of_category_in_drilldown(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -600.0, category="Housing", subcategory="Rent"),
            _make_group(
                "2", "2222222222222222", -400.0, category="Housing", subcategory="Utilities"
            ),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, category="Housing", year=2026)
        assert rc == 0
        assert "60.0%" in output
        assert "40.0%" in output

    def it_should_show_empty_message_for_unknown_category(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -500.0, category="Housing"),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, category="NonExistent", year=2026)
        assert rc == 0
        assert "No transactions found" in output

    def it_should_show_empty_message_when_no_categorized_transactions(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        groups = [
            _make_group("1", "1111111111111111", -500.0, category=None),
        ]
        _build_projections(workspace, groups)
        rc, output = _run_capturing(workspace, year=2026)
        assert rc == 0
        assert "No categorized transactions" in output
