from __future__ import annotations

"""Add or update notes on transactions."""

from gilt.model.account import TransactionGroup
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.transaction_operations_service import TransactionOperationsService
from gilt.workspace import Workspace

from ..console import console, display_transaction_matches, print_error
from ..formatting import fmt_amount_str
from ..mutations import run_confirmed_mutation, validate_single_vs_batch_mode


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

    def row_fn(group: TransactionGroup) -> tuple:
        txn = group.primary
        raw_desc = (txn.description or "").strip()
        desc_display = _highlight_prefix(raw_desc, desc_prefix) if desc_prefix else raw_desc
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


def _resolve_note_targets(
    service: TransactionOperationsService,
    groups: list[TransactionGroup],
    account: str,
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
    amount: float | None,
) -> list[TransactionGroup] | int:
    """Resolve which transactions to annotate, printing appropriate messages.

    Delegates pure matching to the service and handles console output for
    success/failure feedback.  Returns the matched groups or an exit code.
    """
    if validate_single_vs_batch_mode(txid, description, desc_prefix, pattern) is None:
        return 1

    result = service.find_transaction_targets(
        groups,
        txid=txid,
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
    )

    if isinstance(result, str):
        print_error(result)
        # Exit 2 for bad-input errors (too short, ambiguous, invalid pattern);
        # exit 1 for "not found" (valid query, no matches).
        not_found = result.startswith("No transaction found")
        return 1 if not_found else 2

    if not result:
        return []

    return result


def _print_note_target_summary(
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


def _apply_and_write_notes(
    service: TransactionOperationsService,
    groups: list[TransactionGroup],
    groups_to_update: list[TransactionGroup],
    note_text: str,
    ledger_repo: LedgerRepository,
    account_id: str,
) -> int:
    """Apply notes and write back to CSV."""
    updated_ids = {g.primary.transaction_id for g in groups_to_update}
    updated_groups = []
    for group in groups:
        if group.primary.transaction_id in updated_ids:
            updated_groups.append(service.add_note(group, note_text))
        else:
            updated_groups.append(group)

    ledger_repo.save(account_id, updated_groups)
    return len(groups_to_update)


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
    ledger_repo = LedgerRepository(workspace.ledger_data_dir)

    if not ledger_repo.exists(account):
        print_error(f"Ledger not found: {ledger_repo.ledger_path(account)}")
        return 1

    try:
        groups = ledger_repo.load(account)
    except ValueError as e:
        print_error(f"Error loading ledger: {e}")
        return 1

    if not groups:
        console.print(
            f"[yellow]No transactions found in ledger:[/] {ledger_repo.ledger_path(account)}"
        )
        return 1

    service = TransactionOperationsService()

    result = _resolve_note_targets(
        service, groups, account, txid, description, desc_prefix, pattern, amount
    )
    if isinstance(result, int):
        return result
    groups_to_update = result

    if not groups_to_update:
        console.print("[yellow]No transactions matched the specified criteria.[/yellow]")
        return 1

    _print_note_target_summary(
        groups_to_update, account, txid, description, desc_prefix, pattern, amount
    )

    def display() -> None:
        _display_matches(
            account, groups_to_update, note_text, desc_prefix=desc_prefix if desc_prefix else None
        )

    def apply() -> int:
        count = _apply_and_write_notes(
            service, groups, groups_to_update, note_text, ledger_repo, account
        )
        console.print(
            f"[green]Saved notes to ledger successfully.[/] Applied to {count} transaction(s)."
        )
        return 0

    return run_confirmed_mutation(
        matches=groups_to_update,
        display=display,
        confirm_prompt=f"Add note to {len(groups_to_update)} transaction(s)?",
        assume_yes=assume_yes,
        write=write,
        apply=apply,
    )
