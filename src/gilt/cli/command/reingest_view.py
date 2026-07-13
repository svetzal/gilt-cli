"""Rich rendering functions for the reingest command."""

from __future__ import annotations

from pathlib import Path

from ..console import console


def print_no_source_files(account: str) -> None:
    """Print the message shown when no ingest files match the account."""
    console.print(f"[yellow]No source files matched account '{account}'[/]")


def display_reingest_plan(
    account: str,
    account_files: list[tuple],
    ledger_path: Path,
    purge_plan,
) -> None:
    """Print the reingest plan for the given account."""
    ledger_exists = ledger_path.exists()
    console.print(f"[bold]Reingest plan for account: {account}[/]")
    console.print(f"  Source files: {len(account_files)}")
    for p, _ in account_files:
        console.print(f"    - {p.name}")
    console.print(f"  Ledger file: {ledger_path.name} ({'exists' if ledger_exists else 'missing'})")
    console.print(f"  Events to purge: {len(purge_plan.event_ids)}")
    console.print(f"  Transactions to purge: {len(purge_plan.transaction_ids)}")


def print_removed_ledger(name: str) -> None:
    """Print confirmation that the ledger CSV was removed."""
    console.print(f"[green][ok][/] Removed ledger: {name}")


def print_purge_results(purge_result) -> None:
    """Print the counts of purged events, projections, and cache entries."""
    console.print(f"[green][ok][/] Purged {purge_result.events_purged} events")
    console.print(f"[green][ok][/] Purged {purge_result.projections_purged} projections")
    console.print(
        f"[green][ok][/] Purged {purge_result.cache_entries_purged} cached intelligence entries"
    )


def print_wrote(out_path: Path) -> None:
    """Print confirmation that a normalized ledger file was written."""
    console.print(f"[green][ok][/] Wrote {out_path}")


def print_rebuilding() -> None:
    """Print the projection-rebuild header."""
    console.print("[bold]Rebuilding projections[/]")


def print_transfer_metadata(modified_transfers: int) -> None:
    """Print how many ledger files were updated with transfer metadata."""
    console.print(
        f"[green][ok][/] Updated {modified_transfers} ledger file(s) with transfer metadata"
    )


def print_rebuilt(events_processed: int) -> None:
    """Print confirmation that projections were rebuilt."""
    console.print(f"[green][ok][/] Rebuilt projections from {events_processed} events")


def print_done(written: int, account: str) -> None:
    """Print the final reingest summary line."""
    console.print(f"\nDone. Re-ingested {written} file(s) for account {account}.")
