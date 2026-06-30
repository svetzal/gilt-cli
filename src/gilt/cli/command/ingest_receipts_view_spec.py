"""Specs for ingest_receipts_view.py — Rich rendering for the ingest-receipts command."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO
from pathlib import Path

from rich.console import Console


def _capture(fn) -> str:
    buf = StringIO()
    import gilt.cli.command.ingest_receipts_view as view_mod
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


def _make_receipt():
    from gilt.services.receipt_ingestion_service import ReceiptData

    return ReceiptData(
        vendor="ACME CORP",
        service="Widget Service",
        amount=Decimal("99.99"),
        currency="CAD",
        tax_amount=None,
        tax_type=None,
        receipt_date=date(2025, 6, 1),
        invoice_number="INV-001",
        source_email=None,
        receipt_file=None,
        source_path=Path("/tmp/receipt.json"),
    )


def _make_match_result(status="matched", txn_id="abcd1234"):
    from gilt.services.receipt_ingestion_service import MatchResult

    return MatchResult(
        receipt=_make_receipt(),
        status=status,
        transaction_id=txn_id if status == "matched" else None,
        candidate_count=0,
        current_description="ACME CORP PAYMENT",
        candidates=[],
        match_confidence="high" if status == "matched" else None,
    )


class DescribeDisplaySummary:
    def it_should_show_matched_count(self):
        from gilt.cli.command.ingest_receipts_view import display_summary

        matched = [_make_match_result("matched")]
        output = _capture(
            lambda: display_summary(matched, [], [], 0, 0, write=False, written=0)
        )
        assert "1" in output
        assert "Matched" in output

    def it_should_show_dry_run_message_when_not_writing(self):
        from gilt.cli.command.ingest_receipts_view import display_summary

        matched = [_make_match_result("matched")]
        output = _capture(
            lambda: display_summary(matched, [], [], 0, 0, write=False, written=0)
        )
        assert "dry" in output.lower() or "write" in output.lower()

    def it_should_show_written_count_when_write_is_true(self):
        from gilt.cli.command.ingest_receipts_view import display_summary

        matched = [_make_match_result("matched")]
        output = _capture(
            lambda: display_summary(matched, [], [], 0, 0, write=True, written=1)
        )
        assert "1" in output


class DescribeDisplayResultsTable:
    def it_should_render_vendor_name(self):
        from gilt.cli.command.ingest_receipts_view import display_results_table

        results = [_make_match_result("matched")]
        output = _capture(lambda: display_results_table(results))
        assert "ACME CORP" in output

    def it_should_render_nothing_for_empty_list(self):
        from gilt.cli.command.ingest_receipts_view import display_results_table

        output = _capture(lambda: display_results_table([]))
        assert output.strip() == ""
