from __future__ import annotations

"""Tests for the gilt history command."""

from decimal import Decimal
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from rich.console import Console

from gilt.cli.command.history import run
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.events import TransactionImported
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


def _build_projections(workspace: Workspace, groups: list[TransactionGroup]) -> None:
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
    builder = ProjectionBuilder(workspace.projections_path)
    builder.build_from_scratch(store)


def _make_txn(
    txn_id: str,
    description: str,
    amount: float,
    *,
    account_id: str = "MYBANK_CHQ",
    date: str = "2025-06-01",
    category: str | None = None,
    subcategory: str | None = None,
    currency: str = "CAD",
) -> Transaction:
    return Transaction(
        transaction_id=txn_id,
        date=date,
        description=description,
        amount=amount,
        currency=currency,
        account_id=account_id,
        category=category,
        subcategory=subcategory,
    )


def _make_group(txn: Transaction) -> TransactionGroup:
    return TransactionGroup(group_id=txn.transaction_id, primary=txn)


def _apply_category(
    workspace: Workspace, txn_id: str, category: str, subcategory: str | None
) -> None:
    """Update a transaction's category directly in the projections DB."""
    import sqlite3

    conn = sqlite3.connect(workspace.projections_path)
    try:
        conn.execute(
            "UPDATE transaction_projections SET category = ?, subcategory = ? "
            "WHERE transaction_id = ?",
            (category, subcategory, txn_id),
        )
        conn.commit()
    finally:
        conn.close()


class DescribeHistoryBasicGrouping:
    """history command — groups results by category and subcategory."""

    def it_should_group_by_category_and_subcategory(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                _make_group(_make_txn("aa" * 8, "EXAMPLE PHARMACY PURCHASE", -12.50)),
                _make_group(_make_txn("bb" * 8, "EXAMPLE PHARMACY REFILL", -8.00)),
                _make_group(_make_txn("cc" * 8, "EXAMPLE PHARMACY OTC", -5.00)),
            ]
            _build_projections(workspace, groups)
            _apply_category(workspace, "aa" * 8, "Health", "Pharmacy")
            _apply_category(workspace, "bb" * 8, "Health", "Pharmacy")
            _apply_category(workspace, "cc" * 8, "Health", "OTC")

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(pattern="EXAMPLE PHARMACY", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            # Two distinct subcategory rows: Health:Pharmacy (grouped, count=2) and Health:OTC (count=1)
            assert "Pharmacy" in output
            assert "OTC" in output
            # Count=2 row for Pharmacy and count=1 row for OTC
            assert " 2 " in output
            assert " 1 " in output


class DescribeHistoryCaseInsensitivity:
    """history command — pattern matching is case-insensitive."""

    def it_should_match_pattern_regardless_of_case(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                _make_group(_make_txn("dd" * 8, "ACME CORP PAYMENT", -50.00)),
            ]
            _build_projections(workspace, groups)
            _apply_category(workspace, "dd" * 8, "Work", "Expenses")

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(pattern="acme corp", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            assert "Work" in output


class DescribeHistoryAccountFilter:
    """history command — --account restricts results to one account."""

    def it_should_restrict_to_one_account_when_account_flag_set(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                _make_group(
                    _make_txn(
                        "ee" * 8,
                        "SAMPLE STORE PURCHASE",
                        -30.00,
                        account_id="MYBANK_CHQ",
                    )
                ),
                _make_group(
                    _make_txn(
                        "ff" * 8,
                        "SAMPLE STORE PURCHASE",
                        -30.00,
                        account_id="MYBANK_CC",
                    )
                ),
            ]
            _build_projections(workspace, groups)
            _apply_category(workspace, "ee" * 8, "Shopping", "Retail")
            _apply_category(workspace, "ff" * 8, "Shopping", "Retail")

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(
                    pattern="SAMPLE STORE",
                    account="MYBANK_CHQ",
                    workspace=workspace,
                )

            output = buf.getvalue()
            assert rc == 0
            # Only count=1 row (one account), not 2
            assert " 2 " not in output
            assert " 1 " in output


class DescribeHistoryIncludeUncategorized:
    """history command — uncategorized transactions are excluded by default."""

    def it_should_exclude_uncategorized_by_default(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                _make_group(_make_txn("gg" * 8, "EXAMPLE UTILITY BILL", -80.00)),
            ]
            _build_projections(workspace, groups)
            # No category set — leave uncategorized

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(pattern="EXAMPLE UTILITY", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            assert "No matching" in output

    def it_should_show_uncategorized_row_when_flag_set(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                _make_group(_make_txn("hh" * 8, "EXAMPLE UTILITY BILL", -80.00)),
            ]
            _build_projections(workspace, groups)
            # No category set — leave uncategorized

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(
                    pattern="EXAMPLE UTILITY",
                    include_uncategorized=True,
                    workspace=workspace,
                )

            output = buf.getvalue()
            assert rc == 0
            assert "(uncategorized)" in output


class DescribeHistoryLimit:
    """history command — results are truncated to --limit."""

    def it_should_truncate_results_to_limit(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            # Five distinct categories
            cats = ["CatA", "CatB", "CatC", "CatD", "CatE"]
            txn_ids = [f"{i:016x}" for i in range(len(cats))]
            groups = [
                _make_group(_make_txn(txn_id, "ACME CORP INVOICE", -10.00)) for txn_id in txn_ids
            ]
            _build_projections(workspace, groups)
            for txn_id, cat in zip(txn_ids, cats, strict=True):
                _apply_category(workspace, txn_id, cat, None)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(pattern="ACME CORP", limit=2, workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            # Only 2 rows; count each category name appearance
            present = sum(1 for cat in cats if cat in output)
            assert present == 2


class DescribeHistoryOrdering:
    """history command — rows ordered by count descending."""

    def it_should_order_by_count_descending(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            # CatA×1, CatB×3, CatC×2
            entries = [
                ("a0" * 8, "CatA"),
                ("b0" * 8, "CatB"),
                ("b1" * 8, "CatB"),
                ("b2" * 8, "CatB"),
                ("c0" * 8, "CatC"),
                ("c1" * 8, "CatC"),
            ]
            groups = [
                _make_group(_make_txn(txn_id, "SAMPLE STORE PURCHASE", -5.00))
                for txn_id, _ in entries
            ]
            _build_projections(workspace, groups)
            for txn_id, cat in entries:
                _apply_category(workspace, txn_id, cat, None)

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(pattern="SAMPLE STORE", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            pos_b = output.index("CatB")
            pos_c = output.index("CatC")
            pos_a = output.index("CatA")
            assert pos_b < pos_c < pos_a


class DescribeHistoryEmptyResult:
    """history command — no matches returns 0 with informative message."""

    def it_should_return_zero_and_print_no_match_message(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            groups = [
                _make_group(_make_txn("ii" * 8, "SOME OTHER TRANSACTION", -20.00)),
            ]
            _build_projections(workspace, groups)
            _apply_category(workspace, "ii" * 8, "Food", "Groceries")

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(pattern="NONEXISTENT VENDOR", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            assert "No matching" in output
            assert "NONEXISTENT VENDOR" in output


class DescribeHistoryDateWindow:
    """history command -- date range filtering works correctly."""

    def it_should_filter_to_date_range(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))

            # Three within 2025, two outside
            txns_in = [
                _make_txn("j0" * 8, "EXAMPLE UTILITY BILL", -40.00, date="2025-03-01"),
                _make_txn("j1" * 8, "EXAMPLE UTILITY BILL", -40.00, date="2025-07-15"),
                _make_txn("j2" * 8, "EXAMPLE UTILITY BILL", -40.00, date="2025-12-01"),
            ]
            txns_out = [
                _make_txn("j3" * 8, "EXAMPLE UTILITY BILL", -40.00, date="2024-11-01"),
                _make_txn("j4" * 8, "EXAMPLE UTILITY BILL", -40.00, date="2026-01-10"),
            ]
            groups = [_make_group(t) for t in txns_in + txns_out]
            _build_projections(workspace, groups)
            for t in txns_in + txns_out:
                _apply_category(workspace, t.transaction_id, "Housing", "Utilities")

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(
                    pattern="EXAMPLE UTILITY",
                    date_from="2025-01-01",
                    date_to="2025-12-31",
                    workspace=workspace,
                )

            output = buf.getvalue()
            assert rc == 0
            assert " 3 " in output


class DescribeHistoryDuplicatesExcluded:
    """history command — transactions marked as duplicates are excluded."""

    def it_should_exclude_marked_duplicates(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            import sqlite3

            groups = [
                _make_group(_make_txn("k0" * 8, "EXAMPLE PHARMACY DUPLICATE", -15.00)),
                _make_group(_make_txn("k1" * 8, "EXAMPLE PHARMACY DUPLICATE", -15.00)),
            ]
            _build_projections(workspace, groups)
            _apply_category(workspace, "k0" * 8, "Health", "Pharmacy")
            _apply_category(workspace, "k1" * 8, "Health", "Pharmacy")

            # Mark k1 as a duplicate of k0
            conn = sqlite3.connect(workspace.projections_path)
            try:
                conn.execute(
                    "UPDATE transaction_projections SET is_duplicate = 1, "
                    "primary_transaction_id = ? WHERE transaction_id = ?",
                    ("k0" * 8, "k1" * 8),
                )
                conn.commit()
            finally:
                conn.close()

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(pattern="EXAMPLE PHARMACY DUPLICATE", workspace=workspace)

            output = buf.getvalue()
            assert rc == 0
            assert " 1 " in output
            assert " 2 " not in output


class DescribeHistoryNoProjections:
    """history command — missing projections DB returns exit code 1."""

    def it_should_return_one_when_projections_db_missing(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            # Do not create any projections

            buf = StringIO()
            test_console = Console(file=buf, width=200)
            with patch("gilt.cli.command.history.console", test_console):
                rc = run(pattern="ANY PATTERN", workspace=workspace)

            assert rc == 1
