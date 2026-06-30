"""Specs for summary_view.py — Rich rendering for the summary command."""

from __future__ import annotations

from datetime import date
from io import StringIO

from rich.console import Console


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    con = Console(file=buf, highlight=False, width=200)
    return con, buf


def _make_transaction(category="Utilities", subcategory=None, amount=-50.0):
    from gilt.model.account import Transaction

    return Transaction(
        transaction_id="abcd1234efgh5678",
        date=date(2025, 6, 1),
        description="EXAMPLE UTILITY",
        amount=amount,
        currency="CAD",
        account_id="MYBANK_CHQ",
        category=category,
        subcategory=subcategory,
    )


class DescribeDisplayCategoryTable:
    def it_should_render_category_names(self):
        from gilt.cli.command.summary_view import display_category_table

        con, buf = _make_console()
        txns = [_make_transaction("Utilities")]
        display_category_table(con, txns, year=None, fy_label=None, include_uncategorized=False)
        output = buf.getvalue()
        assert "Utilities" in output

    def it_should_include_fy_label_when_provided(self):
        from gilt.cli.command.summary_view import display_category_table

        con, buf = _make_console()
        txns = [_make_transaction("Utilities")]
        display_category_table(con, txns, year=None, fy_label="fy2025", include_uncategorized=False)
        output = buf.getvalue()
        assert "FY2025" in output

    def it_should_show_empty_message_when_no_transactions(self):
        from gilt.cli.command.summary_view import display_category_table

        con, buf = _make_console()
        display_category_table(con, [], year=None, fy_label=None, include_uncategorized=False)
        output = buf.getvalue()
        assert "No categorized" in output or "No" in output


class DescribeDisplaySubcategoryTable:
    def it_should_render_subcategory_data(self):
        from gilt.cli.command.summary_view import display_subcategory_table

        con, buf = _make_console()
        txns = [_make_transaction("Utilities", subcategory="Internet")]
        display_subcategory_table(con, txns, category="Utilities", year=None, fy_label=None)
        output = buf.getvalue()
        assert "Internet" in output

    def it_should_show_empty_message_when_no_matching_transactions(self):
        from gilt.cli.command.summary_view import display_subcategory_table

        con, buf = _make_console()
        txns = [_make_transaction("Food")]
        display_subcategory_table(con, txns, category="Utilities", year=None, fy_label=None)
        output = buf.getvalue()
        assert "No transactions" in output or "No" in output
