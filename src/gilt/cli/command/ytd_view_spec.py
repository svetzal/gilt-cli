"""Specs for ytd_view.py — Rich rendering for the ytd command."""

from __future__ import annotations

from datetime import date
from io import StringIO
from unittest.mock import MagicMock

from rich.console import Console

from gilt.testing import make_transaction


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.ytd_view as view_mod
    import gilt.cli.console as console_mod

    new_console = Console(file=buf, highlight=False, width=200)
    old_view = view_mod.console
    old_mod = console_mod.console
    view_mod.console = new_console
    console_mod.console = new_console
    try:
        fn()
    finally:
        view_mod.console = old_view
        console_mod.console = old_mod
    return buf.getvalue()


def _make_transaction(account_id="MYBANK_CHQ", amount=-50.0, category="Utilities"):
    return make_transaction(
        transaction_id="abcd1234efgh5678",
        date=date(2025, 6, 1),
        description="EXAMPLE UTILITY PAYMENT",
        amount=amount,
        account_id=account_id,
        category=category,
        subcategory=None,
    )


def _make_query_service(credits=100.0, debits=-200.0, net=-100.0):
    svc = MagicMock()
    totals = MagicMock()
    totals.credits = credits
    totals.debits = debits
    totals.net = net
    svc.get_totals.return_value = totals
    return svc


class DescribeDisplayYtdTable:
    def it_should_render_account_name_in_title(self):
        from gilt.cli.command.ytd_view import display_ytd_table

        txns = [_make_transaction()]
        output = _capture(
            lambda: display_ytd_table(
                txns,
                account="MYBANK_CHQ",
                the_year=2025,
                acct_nature="asset",
                compare=False,
                raw=False,
                query_service=_make_query_service(),
            )
        )
        assert "MYBANK_CHQ" in output

    def it_should_render_year_in_title(self):
        from gilt.cli.command.ytd_view import display_ytd_table

        txns = [_make_transaction()]
        output = _capture(
            lambda: display_ytd_table(
                txns,
                account="MYBANK_CHQ",
                the_year=2025,
                acct_nature="asset",
                compare=False,
                raw=False,
                query_service=_make_query_service(),
            )
        )
        assert "2025" in output

    def it_should_render_transaction_description(self):
        from gilt.cli.command.ytd_view import display_ytd_table

        txns = [_make_transaction()]
        output = _capture(
            lambda: display_ytd_table(
                txns,
                account="MYBANK_CHQ",
                the_year=2025,
                acct_nature="asset",
                compare=False,
                raw=True,
                query_service=_make_query_service(),
            )
        )
        assert "EXAMPLE UTILITY" in output


class DescribePrintNoTransactions:
    def it_should_mention_the_account_and_year(self):
        from gilt.cli.command.ytd_view import print_no_transactions

        output = _capture(lambda: print_no_transactions("MYBANK_CHQ", 2025, compare=False))
        assert "MYBANK_CHQ" in output
        assert "2025" in output
