from __future__ import annotations

"""Add or update notes on transactions."""

from gilt.model.account import TransactionGroup
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.transaction_operations_service import TransactionOperationsService
from gilt.workspace import Workspace

from ..console import print_error
from ..mutations import run_confirmed_mutation, validate_single_vs_batch_mode
from ._errors import CommandAbort
from .note_view import (
    display_matches,
    print_no_matches,
    print_no_transactions_in_ledger,
    print_note_target_summary,
    print_notes_saved,
)


def _find_note_targets(
    service: TransactionOperationsService,
    groups: list[TransactionGroup],
    account: str,
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
    amount: float | None,
) -> list[TransactionGroup]:
    """Resolve which transactions to annotate, printing appropriate messages.

    Delegates pure matching to the service and handles console output for
    success/failure feedback.  Returns the matched groups, or raises CommandAbort
    with exit code 1 (not found) or 2 (bad input).
    """
    if validate_single_vs_batch_mode(txid, description, desc_prefix, pattern) is None:
        raise CommandAbort(1)

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
        raise CommandAbort(1 if not_found else 2)

    if not result:
        return []

    return result


def _save_notes(
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
        raise CommandAbort(1)

    try:
        groups = ledger_repo.load(account)
    except ValueError as e:
        print_error(f"Error loading ledger: {e}")
        raise CommandAbort(1) from None

    if not groups:
        print_no_transactions_in_ledger(ledger_repo.ledger_path(account))
        raise CommandAbort(1)

    service = TransactionOperationsService()
    groups_to_update = _find_note_targets(
        service, groups, account, txid, description, desc_prefix, pattern, amount
    )

    if not groups_to_update:
        print_no_matches()
        raise CommandAbort(1)

    print_note_target_summary(
        groups_to_update, account, txid, description, desc_prefix, pattern, amount
    )

    def display() -> None:
        display_matches(
            account, groups_to_update, note_text, desc_prefix=desc_prefix if desc_prefix else None
        )

    def apply() -> int:
        count = _save_notes(service, groups, groups_to_update, note_text, ledger_repo, account)
        print_notes_saved(count)
        return 0

    return run_confirmed_mutation(
        matches=groups_to_update,
        display=display,
        confirm_prompt=f"Add note to {len(groups_to_update)} transaction(s)?",
        assume_yes=assume_yes,
        write=write,
        apply=apply,
    )
