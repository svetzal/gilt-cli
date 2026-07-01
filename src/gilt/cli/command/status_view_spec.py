"""Specs for status_view.py — Rich rendering for the status command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    con = Console(file=buf, highlight=False, width=200)
    return con, buf


def _make_status_row(account_id="MYBANK_CHQ", days_since=5, total_txns=100, uncategorized=3):
    from gilt.cli.command.status_view import StatusRow

    return StatusRow(
        account_id=account_id,
        latest_txn="2025-06-25",
        days_since_latest=days_since,
        total_txns=total_txns,
        uncategorized=uncategorized,
        mojility_txns=10,
        mojility_w_receipt=8,
        mojility_receipt_pct=80,
    )


class DescribeRender:
    def it_should_render_account_id(self):
        from gilt.cli.command.status_view import render

        con, buf = _make_console()
        rows = [_make_status_row("MYBANK_CHQ")]
        render(rows, stale_threshold=30, fy_label=None, console=con)
        output = buf.getvalue()
        assert "MYBANK_CHQ" in output

    def it_should_include_fy_label_in_header_when_provided(self):
        from gilt.cli.command.status_view import render

        con, buf = _make_console()
        rows = [_make_status_row()]
        render(rows, stale_threshold=30, fy_label="fy2025", console=con)
        output = buf.getvalue()
        assert "FY2025" in output

    def it_should_highlight_stale_accounts(self):
        from gilt.cli.command.status_view import render

        con, buf = _make_console()
        rows = [_make_status_row(days_since=60)]
        render(rows, stale_threshold=30, fy_label=None, console=con)
        output = buf.getvalue()
        assert "⚠" in output

    def it_should_not_highlight_fresh_accounts(self):
        from gilt.cli.command.status_view import render

        con, buf = _make_console()
        rows = [_make_status_row(days_since=5)]
        render(rows, stale_threshold=30, fy_label=None, console=con)
        output = buf.getvalue()
        assert "⚠" not in output
