"""Rich rendering functions for the ingest command."""

from __future__ import annotations

from collections.abc import Iterable
from pathlib import Path

from ..console import console


def display_plan(plan: Iterable[tuple[Path, str | None]], total_files: int) -> None:
    """Print the ingestion/normalization plan preview."""
    console.print("[bold]Ingestion/Normalization Plan[/]")
    console.print(f"Inputs matched: {total_files}")
    for p, acct_id in plan:
        console.print(f"  - {p.name} -> account_id={acct_id or 'UNKNOWN'}")


def print_event_store(path) -> None:
    """Print the active event store path."""
    console.print(f"[dim]Event store: {path}[/]")


def display_pre_counts(counts: dict[str, int]) -> None:
    """Print the transaction counts of existing ledgers before ingest."""
    if not counts:
        return
    console.print("[bold]Loaded existing ledgers (pre-ingest)[/]")
    for name, cnt in sorted(counts.items()):
        console.print(f"  - {name}: {cnt} transactions (groups)")


def display_post_counts(counts: dict[str, int], pre_counts: dict[str, int]) -> None:
    """Print the transaction counts of ledgers after ingest, with deltas."""
    if not counts:
        return
    console.print("[bold]Reloaded ledgers (post-ingest)[/]")
    for name, cnt in sorted(counts.items()):
        delta = cnt - pre_counts.get(name, 0)
        sign = "+" if delta >= 0 else ""
        console.print(f"  - {name}: {cnt} groups ({sign}{delta} change)")


def print_skip(name: str) -> None:
    """Print the skip notice for a file whose account could not be inferred."""
    console.print(
        f"[yellow][skip][/yellow] Could not infer account for {name}; "
        "update config/accounts.yml"
    )


def print_wrote(out_path) -> None:
    """Print confirmation that a normalized ledger file was written."""
    console.print(f"[green][ok][/green] Wrote {out_path}")


def print_transfer_metadata(modified_transfer_count: int) -> None:
    """Print how many ledger files were updated with transfer metadata."""
    console.print(
        f"[green][ok][/green] Updated {modified_transfer_count} "
        "ledger file(s) with transfer metadata"
    )


def print_no_transfers() -> None:
    """Print the message shown when no transfer links were identified."""
    console.print("[dim]No transfer links identified or no updates needed[/]")


def print_processed(events_processed: int) -> None:
    """Print how many new events were processed."""
    console.print(f"[green][ok][/green] Processed {events_processed} new event(s)")


def print_projection_total(total_transactions: int) -> None:
    """Print the total number of transactions in the projections."""
    console.print(f"[dim]Projections: {total_transactions} total transactions[/dim]")


def print_auto_categorized(count: int) -> None:
    """Print how many transactions were auto-categorized via rules."""
    console.print(
        f"[green][ok][/green] Auto-categorized {count} transaction(s) via rules"
    )


def print_event_store_total(latest_event_sequence: int) -> None:
    """Print the total number of events in the event store."""
    console.print(f"[dim]Event store: {latest_event_sequence} events total[/]")


def print_done(written: int, skipped: int) -> None:
    """Print the final ingest summary line."""
    console.print(f"Done. Written={written}, Skipped={skipped}")
