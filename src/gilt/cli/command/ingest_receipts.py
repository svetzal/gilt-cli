"""
Command module for `gilt ingest-receipts`.

Reads mailctl.receipt.v1 JSON sidecar files, matches them to existing bank
transactions, and emits TransactionEnriched events.

Dry-run by default. Use --write to persist events.
"""

from __future__ import annotations

import json
from pathlib import Path

from rich.prompt import Prompt
from rich.table import Table

from gilt.services.receipt_ingestion_service import (
    DEFAULT_VENDOR_PATTERNS,
    MatchResult,
    batch_match_receipts,
    filter_receipts_by_year,
    find_already_ingested_invoices,
    load_receipt_file,
    scan_receipt_files,
)
from gilt.workspace import Workspace

from .util import console, fmt_amount_str, print_dry_run_message, print_error


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
        amount_str = fmt_amount_str(receipt.amount)
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
            receipt.vendor,
            amount_str,
            str(receipt.receipt_date),
            receipt.invoice_number or "",
            status,
            details,
        )

    console.print(table)


def _resolve_ambiguous_interactively(ambiguous: list[MatchResult]) -> list[MatchResult]:
    """Prompt the user to disambiguate ambiguous matches. Returns resolved items."""
    resolved: list[MatchResult] = []

    for r in ambiguous:
        receipt = r.receipt
        tax_str = f" + ${receipt.tax_amount:.2f} {receipt.tax_type}" if receipt.tax_amount else ""
        subtotal = receipt.amount
        total = subtotal + receipt.tax_amount if receipt.tax_amount else subtotal

        console.print("\n[bold]Ambiguous receipt:[/bold]")
        console.print(f"  Vendor: {receipt.vendor}")
        if receipt.service:
            console.print(f"  Service: {receipt.service}")
        console.print(f"  Amount: ${subtotal:.2f}{tax_str} = ${total:.2f}")
        console.print(f"  Date: {receipt.receipt_date}")
        if receipt.invoice_number:
            console.print(f"  Invoice: {receipt.invoice_number}")
        console.print()

        for i, candidate in enumerate(r.candidates, 1):
            txid = candidate["transaction_id"][:8]
            txn_date = candidate.get("transaction_date", "")
            txn_amount = candidate.get("amount", "")
            desc = candidate.get("canonical_description", "")
            acct = candidate.get("account_id", "")
            console.print(f"  {i}) {txid}  {txn_date}  ${txn_amount}  {desc}  [{acct}]")

        console.print()
        valid_choices = [str(i) for i in range(1, len(r.candidates) + 1)] + ["s", "S"]
        choice = Prompt.ask(
            f"Select [1-{len(r.candidates)}/s to skip]",
            choices=valid_choices,
            show_choices=False,
        )

        if choice.lower() == "s":
            continue

        selected = r.candidates[int(choice) - 1]
        resolved.append(
            MatchResult(
                receipt=receipt,
                status="matched",
                transaction_id=selected["transaction_id"],
                candidate_count=r.candidate_count,
                current_description=selected.get("canonical_description", ""),
                candidates=r.candidates,
                match_confidence="user-selected",
            )
        )

    return resolved


def _filter_paths_by_year(json_paths: list[Path], year: int) -> list[Path]:
    """Load and filter receipt files by year, warning on any that fail to parse."""
    all_receipts = []
    skip_count = 0
    for p in json_paths:
        try:
            all_receipts.append(load_receipt_file(p))
        except (json.JSONDecodeError, OSError, ValueError) as e:
            console.print(f"[yellow]Warning: skipping {p.name} — {e}[/yellow]")
            skip_count += 1
    if skip_count:
        console.print(f"[yellow]Skipped {skip_count} receipt file(s) due to errors.[/yellow]")
    return [r.source_path for r in filter_receipts_by_year(all_receipts, year)]


def run(
    *,
    workspace: Workspace,
    source: Path,
    write: bool = False,
    year: int | None = None,
    account: str | None = None,
    interactive: bool = False,
) -> int:
    """Run the ingest-receipts command."""
    from gilt.model.events import TransactionEnriched
    from gilt.storage.event_store import EventStore
    from gilt.storage.projection import ProjectionBuilder

    if not source.is_dir():
        print_error(f"Source directory not found: {source}")
        return 1

    json_paths = scan_receipt_files(source)
    if year is not None:
        json_paths = _filter_paths_by_year(json_paths, year)
    if not json_paths:
        console.print("[yellow]No receipt JSON files found.[/yellow]")
        return 0

    store = EventStore(str(workspace.event_store_path))
    existing_events = store.get_events_by_type("TransactionEnriched")
    ingested_invoices = find_already_ingested_invoices(existing_events)

    projection_builder = ProjectionBuilder(workspace.projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    batch = batch_match_receipts(
        json_paths,
        all_transactions,
        ingested_invoices,
        account_id=account,
        vendor_patterns=DEFAULT_VENDOR_PATTERNS,
    )

    matched = list(batch.matched)
    ambiguous = list(batch.ambiguous)
    unmatched = batch.unmatched
    skipped_already_ingested = batch.skipped_already_ingested
    skipped_parse_errors = batch.skipped_parse_errors

    _display_results_table(matched + ambiguous + unmatched)

    if interactive and ambiguous:
        resolved = _resolve_ambiguous_interactively(ambiguous)
        matched.extend(resolved)
        ambiguous = [r for r in ambiguous if r not in resolved]

    written = 0
    if write and matched:
        for r in matched:
            receipt = r.receipt
            event = TransactionEnriched(
                transaction_id=r.transaction_id,
                vendor=receipt.vendor,
                service=receipt.service,
                invoice_number=receipt.invoice_number,
                tax_amount=receipt.tax_amount,
                tax_type=receipt.tax_type,
                currency=receipt.currency,
                receipt_file=receipt.receipt_file,
                enrichment_source=str(receipt.source_path),
                source_email=receipt.source_email,
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
        print_dry_run_message(detail=f"{len(matched)} enrichment(s)")

    return 0
