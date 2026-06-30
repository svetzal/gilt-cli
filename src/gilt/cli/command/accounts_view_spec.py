"""Specs for accounts_view.py — Rich rendering for the accounts command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.accounts_view as view_mod
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


class DescribeDisplayAccountsTable:
    def it_should_list_account_ids_and_descriptions(self):
        from gilt.cli.command.accounts_view import display_accounts_table

        mapping = {"MYBANK_CHQ": "MyBank Chequing", "MYBANK_CC": "MyBank Credit Card"}
        output = _capture(lambda: display_accounts_table(mapping))
        assert "MYBANK_CHQ" in output
        assert "MyBank Chequing" in output

    def it_should_sort_accounts_alphabetically(self):
        from gilt.cli.command.accounts_view import display_accounts_table

        # MYBANK_CC sorts before MYBANK_CHQ alphabetically
        mapping = {"MYBANK_CHQ": "Chequing", "BANK2_BIZ": "Business"}
        output = _capture(lambda: display_accounts_table(mapping))
        biz_pos = output.find("BANK2_BIZ")
        chq_pos = output.find("MYBANK_CHQ")
        assert biz_pos < chq_pos

    def it_should_render_the_available_accounts_title(self):
        from gilt.cli.command.accounts_view import display_accounts_table

        output = _capture(lambda: display_accounts_table({"MYBANK_CHQ": "Chequing"}))
        assert "Available Accounts" in output
