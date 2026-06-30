"""Specs for receipts_view.py — Rich rendering for the receipts command."""

from __future__ import annotations

from io import StringIO

from rich.console import Console


def _make_console() -> tuple[Console, StringIO]:
    buf = StringIO()
    con = Console(file=buf, highlight=False, width=200)
    return con, buf


def _make_coverage_result(with_rows=True, with_missing=False):
    from gilt.services.receipts_service import CoverageRow, MissingReceiptRow, ReceiptCoverageResult

    coverage_rows = []
    if with_rows:
        coverage_rows = [
            CoverageRow(
                category="Mojility",
                subcategory="Software",
                account_id="MYBANK_CC",
                total_txns=10,
                with_receipt=8,
                without_receipt=2,
                coverage_pct=80,
                net_amount=-500.0,
            )
        ]

    missing_rows = []
    if with_missing:
        missing_rows = [
            MissingReceiptRow(
                transaction_id="abcd1234efgh5678",
                date="2025-06-01",
                description="ACME CORP SUBSCRIPTION",
                amount=-99.99,
                account_id="MYBANK_CC",
            )
        ]

    return ReceiptCoverageResult(coverage_rows=coverage_rows, missing_rows=missing_rows)


class DescribeRenderSummary:
    def it_should_render_coverage_table_title(self):
        from gilt.cli.command.receipts_view import render_summary

        con, buf = _make_console()
        result = _make_coverage_result()
        render_summary(result, category="Mojility", by_account=False, fy_label=None, con=con)
        output = buf.getvalue()
        assert "Mojility" in output

    def it_should_include_fy_label_in_title_when_provided(self):
        from gilt.cli.command.receipts_view import render_summary

        con, buf = _make_console()
        result = _make_coverage_result()
        render_summary(result, category="Mojility", by_account=False, fy_label="fy2025", con=con)
        output = buf.getvalue()
        assert "FY2025" in output

    def it_should_show_total_line(self):
        from gilt.cli.command.receipts_view import render_summary

        con, buf = _make_console()
        result = _make_coverage_result()
        render_summary(result, category="Mojility", by_account=False, fy_label=None, con=con)
        output = buf.getvalue()
        assert "Total" in output


class DescribeRenderMissing:
    def it_should_show_all_have_receipts_message_when_no_missing(self):
        from gilt.cli.command.receipts_view import render_missing

        con, buf = _make_console()
        result = _make_coverage_result(with_rows=True, with_missing=False)
        render_missing(result, con)
        output = buf.getvalue()
        assert "All" in output or "receipts" in output

    def it_should_render_missing_transaction_ids(self):
        from gilt.cli.command.receipts_view import render_missing

        con, buf = _make_console()
        result = _make_coverage_result(with_rows=True, with_missing=True)
        render_missing(result, con)
        output = buf.getvalue()
        assert "abcd1234" in output
