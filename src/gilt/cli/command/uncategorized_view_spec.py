"""Specs for uncategorized_view.py — Rich rendering for the uncategorized command."""

from __future__ import annotations

from datetime import date
from io import StringIO

from rich.console import Console


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    con = Console(file=buf, highlight=False, width=200)
    return con, buf


def _make_transaction(account_id="MYBANK_CHQ", amount=-50.0):
    from gilt.model.account import Transaction

    return Transaction(
        transaction_id="abcd1234efgh5678",
        date=date(2025, 6, 1),
        description="EXAMPLE UTILITY PAYMENT",
        amount=amount,
        currency="CAD",
        account_id=account_id,
        category=None,
        subcategory=None,
    )


class DescribeDisplayUncategorizedTable:
    def it_should_render_transaction_description(self):
        from gilt.cli.command.uncategorized_view import display_uncategorized_table

        con, buf = _make_console()
        txns = [_make_transaction()]
        display_uncategorized_table(con, txns, year=None)
        output = buf.getvalue()
        assert "EXAMPLE UTILITY" in output

    def it_should_render_table_title(self):
        from gilt.cli.command.uncategorized_view import display_uncategorized_table

        con, buf = _make_console()
        txns = [_make_transaction()]
        display_uncategorized_table(con, txns, year=None)
        output = buf.getvalue()
        assert "Uncategorized" in output

    def it_should_include_fy_label_in_title_when_provided(self):
        from gilt.cli.command.uncategorized_view import display_uncategorized_table

        con, buf = _make_console()
        txns = [_make_transaction()]
        display_uncategorized_table(con, txns, year=None, fy_label="fy2025")
        output = buf.getvalue()
        assert "FY2025" in output


class DescribeDisplaySummary:
    def it_should_show_total_uncategorized_count(self):
        from gilt.cli.command.uncategorized_view import display_summary

        con, buf = _make_console()
        txns = [_make_transaction()]
        display_summary(con, total_count=5, limit=None, remaining=0, transactions=txns)
        output = buf.getvalue()
        assert "5" in output

    def it_should_show_tip_to_use_categorize(self):
        from gilt.cli.command.uncategorized_view import display_summary

        con, buf = _make_console()
        txns = [_make_transaction()]
        display_summary(con, total_count=1, limit=None, remaining=0, transactions=txns)
        output = buf.getvalue()
        assert "categorize" in output.lower()
