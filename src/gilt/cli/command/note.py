from __future__ import annotations

"""Add or update notes on transactions."""

from rich.table import Table

from gilt.model.account import TransactionGroup
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv
from gilt.services.transaction_operations_service import (
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.workspace import Workspace

from .util import console


def _highlight_prefix(desc: str, prefix: str, style: str = "bold yellow") -> str:
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


def _display_matches(
    account: str,
    groups: list[TransactionGroup],
    note_text: str,
    desc_prefix: str | None = None,
) -> None:
    """Display matched transactions in a table."""
    table = Table(title="Matched Transactions", show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Current Note", style="dim")
    table.add_column("→ New Note", style="green")

    for group in groups[:50]:  # Limit display to 50
        txn = group.primary
        raw_desc = (txn.description or "").strip()
        desc_display = _highlight_prefix(raw_desc, desc_prefix) if desc_prefix else raw_desc

        table.add_row(
            account,
            txn.transaction_id[:8],
            str(txn.date),
            desc_display[:40],
            f"{txn.amount:,.0f}",
            (txn.notes or "")[:30] if txn.notes else "—",
            note_text[:30],
        )

    console.print(table)

    if len(groups) > 50:
        console.print(f"[dim]... and {len(groups) - 50} more[/]")


def _find_single_transaction(
    service: TransactionOperationsService,
    txid: str,
    groups: list[TransactionGroup],
) -> list[TransactionGroup] | int:
    """Find a single transaction by ID prefix. Returns matches or exit code."""
    prefix = txid.strip().lower()
    if len(prefix) < 8:
        console.print(
            f"[red]Error:[/red] Transaction ID prefix must be at least 8 characters. Got: {len(prefix)}"
        )
        return 2

    result = service.find_by_id_prefix(prefix, groups)

    if result.type == "not_found":
        console.print(f"[yellow]No transaction found matching ID prefix[/] [bold]{prefix}[/]")
        return 1

    if result.type == "ambiguous":
        sample = []
        for g in result.matches[:5]:
            t = g.primary
            sample.append(
                f"{t.date} id={t.transaction_id[:8]} amt={t.amount} desc='{(t.description or '').strip()}'"
            )
        console.print(
            f"[yellow]Ambiguous prefix[/] [bold]{prefix}[/]: matches {len(result.matches)} transactions. "
            + (" Examples: " + "; ".join(sample) if sample else "")
        )
        console.print("Refine --txid with more characters to disambiguate.")
        return 2

    console.print(f"Will set note for transaction {result.transaction.primary.transaction_id[:8]}")
    return [result.transaction]


def _find_batch_transactions(
    service: TransactionOperationsService,
    groups: list[TransactionGroup],
    account: str,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
    amount: float | None,
) -> list[TransactionGroup] | int:
    """Find transactions by batch criteria. Returns matches or exit code."""
    if not any([description, desc_prefix, pattern]):
        console.print(
            "[red]Error:[/red] Must specify either --txid/-t for single mode, "
            "or one of --description/-d, --desc-prefix/-p, --pattern for batch mode."
        )
        return 1

    if pattern:
        import re
        try:
            re.compile(pattern)
        except re.error as e:
            console.print(f"[red]Invalid regex pattern:[/red] {e}")
            return 2

    criteria = SearchCriteria(description=description, desc_prefix=desc_prefix, pattern=pattern, amount=amount)
    preview = service.find_by_criteria(criteria, groups)

    if not preview.matched_groups:
        console.print("[yellow]No transactions matched the specified criteria.[/yellow]")
        return 1

    if preview.used_sign_insensitive:
        console.print(
            "[dim]Note: matched by absolute amount since no signed matches were found. "
            "Ledger stores debits as negative amounts.[/dim]"
        )

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
        f"Will set note for {len(preview.matched_groups)} transactions in {account} "
        f"matching {' and '.join(criteria_parts)}."
    )
    return preview.matched_groups


def _apply_and_write_notes(
    service: TransactionOperationsService,
    groups: list[TransactionGroup],
    groups_to_update: list[TransactionGroup],
    note_text: str,
    ledger_path,
) -> None:
    """Apply notes and write back to CSV."""
    updated_ids = {g.primary.transaction_id for g in groups_to_update}
    updated_groups = []
    for group in groups:
        if group.primary.transaction_id in updated_ids:
            updated_groups.append(service.add_note(group, note_text))
        else:
            updated_groups.append(group)

    csv_text = dump_ledger_csv(updated_groups)
    ledger_path.write_text(csv_text, encoding="utf-8")

    console.print(
        f"[green]Saved notes to ledger successfully.[/] Applied to {len(groups_to_update)} transaction(s)."
    )


def run(
    *,
    account: str,
    txid: str | None = None,
    note_text: str,
    description: str | None = None,
    desc_prefix: str | None = None,
    pattern: str | None = None,
    amount: float | None = None,
    assume_yes: bool = False,
    workspace: Workspace,
    write: bool = False,
) -> int:
    """Attach or update notes on transactions in the account ledger."""
    data_dir = workspace.ledger_data_dir
    ledger_path = data_dir / f"{account}.csv"

    if not ledger_path.exists():
        console.print(f"[red]Error:[/red] Ledger not found: {ledger_path}")
        return 1

    text = ledger_path.read_text(encoding="utf-8")
    try:
        groups = load_ledger_csv(text)
    except Exception as e:
        console.print(f"[red]Error loading ledger:[/red] {e}")
        return 1

    if not groups:
        console.print(f"[yellow]No transactions found in ledger:[/] {ledger_path}")
        return 1

    service = TransactionOperationsService()

    if txid:
        result = _find_single_transaction(service, txid, groups)
    else:
        result = _find_batch_transactions(service, groups, account, description, desc_prefix, pattern, amount)

    if isinstance(result, int):
        return result
    groups_to_update = result

    _display_matches(account, groups_to_update, note_text, desc_prefix=desc_prefix if desc_prefix else None)

    if not write:
        console.print("\n[dim]Dry-run: no changes written. Use --write to persist.[/]")
        return 0

    if not assume_yes:
        console.print("\n[yellow]Warning:[/yellow] This will update notes in the ledger CSV.")
        response = input("Proceed? (y/N): ").strip().lower()
        if response != "y":
            console.print("[dim]Aborted.[/]")
            return 0

    _apply_and_write_notes(service, groups, groups_to_update, note_text, ledger_path)
    return 0
