"""
Command module for `gilt ingest-receipts`.

Reads mailctl.receipt.v1 JSON sidecar files, matches them to existing bank
transactions, and emits TransactionEnriched events.

Dry-run by default. Use --write to persist events.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.table import Table

from gilt.services.receipt_ingestion_service import (
    MatchResult,
    ReceiptData,
    find_already_ingested_invoices,
    match_receipt_to_transactions,
    scan_receipt_files,
)
from gilt.workspace import Workspace

# Default vendor → description-substring map for receipt matching.
# When a receipt's vendor matches a key here, exact and FX strategies
# require the bank description to contain at least one substring.
_DEFAULT_VENDOR_PATTERNS: dict[str, list[str]] = {
    "apple": ["APPLE.COM/BILL", "APPLE.COM"],
    "github": ["GITHUB"],
    "paddle": ["PADDLE"],
    "zoom": ["ZOOM"],
    "suno": ["SUNO"],
    "costco": ["COSTCO"],
    "vevor": ["VEVOR"],
    "lyft": ["LYFT"],
    "feel heal grow": ["FEELHEALGRO"],
    "anthropic": ["ANTHROPIC", "CLAUDE"],
    "paypal": ["PAYPAL"],
    "microsoft": ["MICROSOFT"],
    "canadian tire": ["CANADIAN TIRE"],
    "best buy": ["BEST BUY"],
}

from .util import console


def _parse_and_match_receipts(
    json_paths, ingested_invoices, all_transactions, account,
) -> tuple[list[MatchResult], int, int]:
    """Parse receipt files and match to transactions. Returns (results, skipped_ingested, skipped_errors)."""
    results: list[MatchResult] = []
    skipped_already_ingested = 0
    skipped_parse_errors = 0

    for path in json_paths:
        try:
            receipt = ReceiptData.from_json_file(path)
        except (ValueError, json.JSONDecodeError, KeyError) as e:
            console.print(f"[yellow]Warning:[/yellow] Skipping {path.name}: {e}")
            skipped_parse_errors += 1
            continue

        if receipt.amount is None:
            console.print(f"[yellow]Warning:[/yellow] Skipping {path.name}: no amount")
            skipped_parse_errors += 1
            continue

        if receipt.invoice_number and receipt.invoice_number in ingested_invoices:
            skipped_already_ingested += 1
            continue

        result = match_receipt_to_transactions(
            receipt, all_transactions, account_id=account, vendor_patterns=_DEFAULT_VENDOR_PATTERNS,
        )
        results.append(result)

    return results, skipped_already_ingested, skipped_parse_errors


def _display_results_table(results: list[MatchResult]) -> None:
    """Display receipt matching results in a table."""
    if not results:
        return

    table = Table(title="Receipt Matching Results", show_lines=False)
    table.add_column("Vendor", style="white", no_wrap=True, max_width=30)
    table.add_column("Amount", justify="right", style="yellow")
    table.add_column("Date", style="cyan", no_wrap=True)
    table.add_column("Invoice #", style="dim")
    table.add_column("Status", no_wrap=True)
    table.add_column("Details", style="dim", max_width=50)

    for r in results:
        receipt = r.receipt
        amount_str = f"${receipt.amount:,.2f}"
        confidence = r.match_confidence or ""

        if r.status == "matched":
            status = f"[green]matched ({confidence})[/green]"
            details = f"txid={r.transaction_id[:8]}"
            if r.current_description:
                details += f"  {r.current_description[:40]}"
        elif r.status == "ambiguous":
            status = f"[yellow]ambiguous ({r.candidate_count})[/yellow]"
            details = ", ".join(c["transaction_id"][:8] for c in r.candidates[:5])
        else:
            status = "[red]unmatched[/red]"
            details = ""

        table.add_row(
            receipt.vendor, amount_str, str(receipt.receipt_date),
            receipt.invoice_number or "", status, details,
        )

    console.print(table)


def run(
    *,
    workspace: Workspace,
    source: Path,
    write: bool = False,
    year: int | None = None,
    account: str | None = None,
) -> int:
    """Run the ingest-receipts command."""
    from gilt.model.events import TransactionEnriched
    from gilt.storage.event_store import EventStore
    from gilt.storage.projection import ProjectionBuilder

    if not source.is_dir():
        console.print(f"[red]Error:[/red] Source directory not found: {source}")
        return 1

    json_paths = scan_receipt_files(source, year=year)
    if not json_paths:
        console.print("[yellow]No receipt JSON files found.[/yellow]")
        return 0

    store = EventStore(str(workspace.event_store_path))
    existing_events = store.get_events_by_type("TransactionEnriched")
    ingested_invoices = find_already_ingested_invoices(existing_events)

    projection_builder = ProjectionBuilder(workspace.projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    results, skipped_already_ingested, skipped_parse_errors = _parse_and_match_receipts(
        json_paths, ingested_invoices, all_transactions, account,
    )

    matched = [r for r in results if r.status == "matched"]
    ambiguous = [r for r in results if r.status == "ambiguous"]
    unmatched = [r for r in results if r.status == "unmatched"]

    _display_results_table(results)

    written = 0
    if write and matched:
        for r in matched:
            receipt = r.receipt
            event = TransactionEnriched(
                transaction_id=r.transaction_id, vendor=receipt.vendor,
                service=receipt.service, invoice_number=receipt.invoice_number,
                tax_amount=receipt.tax_amount, tax_type=receipt.tax_type,
                currency=receipt.currency, receipt_file=receipt.receipt_file,
                enrichment_source=str(receipt.source_path), source_email=receipt.source_email,
                match_confidence=r.match_confidence,
            )
            store.append_event(event)
            written += 1

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Matched: {len(matched)}")
    console.print(f"  Ambiguous: {len(ambiguous)}")
    console.print(f"  Unmatched: {len(unmatched)}")
    console.print(f"  Already ingested: {skipped_already_ingested}")
    if skipped_parse_errors:
        console.print(f"  Parse errors: {skipped_parse_errors}")

    if write and written > 0:
        console.print(f"\n[green]{written} TransactionEnriched event(s) written.[/green]")
        console.print("[dim]Tip: Run 'gilt rebuild-projections' to update projections.[/dim]")
    elif not write and matched:
        console.print(f"\n[dim]Dry-run: use --write to persist {len(matched)} enrichment(s)[/dim]")

    return 0
