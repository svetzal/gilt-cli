"""Rich rendering functions for the ingest-receipts command."""

from __future__ import annotations

from rich.table import Table

from gilt.services.receipt_ingestion_service import MatchResult

from ..console import console
from ..formatting import fmt_amount_str


def print_parse_warnings(warnings: list[str]) -> None:
    """Print per-file parse warnings and a skipped-count summary."""
    for w in warnings:
        console.print(f"[yellow]Warning: {w}[/yellow]")
    if warnings:
        console.print(f"[yellow]Skipped {len(warnings)} receipt file(s) due to errors.[/yellow]")


def print_no_receipts() -> None:
    """Print the message shown when no receipt JSON files are found."""
    console.print("[yellow]No receipt JSON files found.[/yellow]")


def display_match_summary(
    matched: list[MatchResult],
    ambiguous: list[MatchResult],
    unmatched: list[MatchResult],
    skipped_already_ingested: int,
    skipped_parse_errors: int,
) -> None:
    """Print the receipt-matching summary counts (shown in both dry-run and write modes)."""
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Matched: {len(matched)}")
    console.print(f"  Ambiguous: {len(ambiguous)}")
    console.print(f"  Unmatched: {len(unmatched)}")
    console.print(f"  Already ingested: {skipped_already_ingested}")
    if skipped_parse_errors:
        console.print(f"  Parse errors: {skipped_parse_errors}")


def print_events_written(written: int) -> None:
    """Print confirmation of how many enrichment events were persisted."""
    if written > 0:
        console.print(f"\n[green]{written} TransactionEnriched event(s) written.[/green]")
        console.print("[dim]Tip: Run 'gilt rebuild-projections' to update projections.[/dim]")


def display_results_table(results: list[MatchResult]) -> None:
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
