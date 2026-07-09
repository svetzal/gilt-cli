"""Rich rendering functions for the note command."""

from __future__ import annotations

from pathlib import Path

from gilt.model.account import TransactionGroup

from ..console import console, display_transaction_matches
from ..formatting import fmt_amount_str


def highlight_prefix(desc: str, prefix: str, style: str = "bold yellow") -> str:
    """Return description with the matching prefix highlighted using Rich markup.

    Case-insensitive match at the start only; preserves original casing in the output.
    If prefix does not match, returns desc unchanged.
    """
    d = desc or ""
    p = (prefix or "").strip().lower()
    if not p:
        return d
    if d.lower().startswith(p):
        n = len(p)
        return f"[{style}]{d[:n]}[/]{d[n:]}"
    return d


def display_matches(
    account: str,
    groups: list[TransactionGroup],
    note_text: str,
    desc_prefix: str | None = None,
) -> None:
    """Display matched transactions in a table."""

    def row_fn(group: TransactionGroup) -> tuple:
        txn = group.primary
        raw_desc = (txn.description or "").strip()
        desc_display = highlight_prefix(raw_desc, desc_prefix) if desc_prefix else raw_desc
        return (
            account,
            txn.transaction_id[:8],
            str(txn.date),
            desc_display[:40],
            fmt_amount_str(txn.amount),
            (txn.notes or "")[:30] if txn.notes else "—",
            note_text[:30],
        )

    display_transaction_matches(
        "Matched Transactions",
        [("Current Note", {"style": "dim"}), ("→ New Note", {"style": "green"})],
        groups,
        row_fn,
    )


def print_note_target_summary(
    groups_to_update: list[TransactionGroup],
    account: str,
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
    amount: float | None,
) -> None:
    """Print a summary of which transactions will be annotated."""
    if txid:
        console.print(
            f"Will set note for transaction {groups_to_update[0].primary.transaction_id[:8]}"
        )
        return
    criteria_parts = []
    if description:
        criteria_parts.append(f"description='{description}'")
    if desc_prefix:
        criteria_parts.append(f"description_prefix='{desc_prefix}'")
    if pattern:
        criteria_parts.append(f"pattern='{pattern}'")
    if amount is not None:
        criteria_parts.append(f"amount={amount}")
    console.print(
        f"Will set note for {len(groups_to_update)} transactions in {account} "
        f"matching {' and '.join(criteria_parts)}."
    )


def print_no_transactions_in_ledger(path: Path) -> None:
    """Print a message when the ledger contains no transactions."""
    console.print(f"[yellow]No transactions found in ledger:[/] {path}")


def print_no_matches() -> None:
    """Print a message when no transactions matched the specified criteria."""
    console.print("[yellow]No transactions matched the specified criteria.[/yellow]")


def print_notes_saved(count: int) -> None:
    """Print a confirmation that notes were saved to the ledger."""
    console.print(
        f"[green]Saved notes to ledger successfully.[/] Applied to {count} transaction(s)."
    )
