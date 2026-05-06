"""Pure table-building functions for the gilt CLI.

All functions in this module return Rich Table objects. They have no side effects
and do not import from util.py (to avoid circular imports).
"""

from __future__ import annotations

from rich.table import Table

from gilt.model.duplicate import TransactionPair


def create_transaction_table(title: str, extra_columns: list[tuple[str, dict]]) -> Table:
    """Create a Rich Table with 5 standard transaction columns plus any extra columns.

    The standard columns are: Account (cyan/no_wrap), TxnID (blue/no_wrap),
    Date (white), Description (white), Amount (yellow/right).

    Args:
        title: The table title.
        extra_columns: List of (header, kwargs) pairs appended after the base columns.
            kwargs are keyword arguments for ``Table.add_column`` (e.g. ``{"style": "green"}``).
    """
    table = Table(title=title, show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    for header, kwargs in extra_columns:
        table.add_column(header, **kwargs)
    return table


def create_duplicate_pair_table(title: str, pair: TransactionPair) -> Table:
    """Create a Rich Table comparing two transactions in a potential duplicate pair.

    Renders a three-column comparison: Field | Latest (1) | Original (2).
    Includes a Source File row when the pair has ``txn1_source_file`` and
    ``txn2_source_file`` attributes.

    Args:
        title: The table title (typically includes match index and confidence).
        pair: A TransactionPair-like object with txn1_*/txn2_* attributes.
    """
    table = Table(title=title, show_header=True, show_lines=True)
    table.add_column("Field", style="cyan")
    table.add_column("Latest (1)", style="magenta")
    table.add_column("Original (2)", style="yellow")

    table.add_row("ID", pair.txn2_id[:8], pair.txn1_id[:8])
    table.add_row("Date", str(pair.txn2_date), str(pair.txn1_date))
    table.add_row("Account", pair.txn2_account, pair.txn1_account)
    table.add_row("Amount", f"{pair.txn2_amount:.2f}", f"{pair.txn1_amount:.2f}")
    table.add_row("Description", pair.txn2_description, pair.txn1_description)

    if hasattr(pair, "txn1_source_file") and hasattr(pair, "txn2_source_file"):
        src1 = pair.txn1_source_file or "[dim]unknown[/dim]"
        src2 = pair.txn2_source_file or "[dim]unknown[/dim]"
        table.add_row("Source File", src2, src1)

    return table


__all__ = ["create_transaction_table", "create_duplicate_pair_table"]
