from __future__ import annotations

"""Categorize transactions (single or batch mode)."""

import logging
import sys
from pathlib import Path

import typer

from gilt.model.account import TransactionGroup
from gilt.model.category_io import load_categories_config
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_service import CategorizationService
from gilt.services.transaction_operations_service import (
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.workspace import Workspace

from .util import (
    apply_categorization_updates,
    console,
    display_transaction_matches,
    find_matches_by_criteria,
    fmt_amount_str,
    group_by_account,
    load_account_transactions,
    load_event_store,
    parse_category_path,
    print_dry_run_message,
    print_error,
    require_event_sourcing,
    validate_single_vs_batch_mode,
)

logger = logging.getLogger(__name__)


def _find_account_ledgers(data_dir: Path, account: str | None) -> list[Path]:
    """Find ledger files to process."""
    repo = LedgerRepository(data_dir)
    if account:
        if not repo.exists(account):
            return []
        return [repo.ledger_path(account)]
    else:
        return repo.ledger_paths()




def _resolve_targets(
    all_transactions: list[dict],
    single_mode: bool,
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
    amount: float | None,
    service: TransactionOperationsService,
) -> list[tuple[str, TransactionGroup]] | None:
    """Build groups, apply search criteria, and return matched (account_id, group) pairs.

    Returns None on error (invalid pattern, ambiguous ID, etc.).
    """
    criteria = SearchCriteria(
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
    )
    groups_by_account = group_by_account(all_transactions)
    return find_matches_by_criteria(
        groups_by_account, criteria, service, txid=txid if single_mode else None
    )


def _confirm_batch(total_matched: int, single_mode: bool, assume_yes: bool, write: bool) -> bool:
    """Returns True if processing should proceed, False if the user cancelled."""
    if single_mode or total_matched <= 1 or assume_yes:
        return True
    if not write:
        return True
    import sys

    if sys.stdin.isatty() and not typer.confirm(f"Categorize {total_matched} transaction(s)?"):
        console.print("Cancelled")
        return False
    return True


def _confirm_and_apply(
    all_matches: list[tuple[str, TransactionGroup]],
    category: str,
    subcategory: str | None,
    single_mode: bool,
    assume_yes: bool,
    write: bool,
    workspace: Workspace,
    categorization_service: CategorizationService,
) -> int:
    """Display matches, confirm, apply categorization, and write back. Returns exit code."""
    total_matched = len(all_matches)

    _display_matches(all_matches, category, subcategory)

    if not _confirm_batch(total_matched, single_mode, assume_yes, write):
        return 0

    if not write:
        print_dry_run_message()
        return 0

    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1

    result = categorization_service.run_categorization(
        [group for _, group in all_matches],
        category,
        subcategory,
    )

    account_by_txn_id = {group.primary.transaction_id: acct for acct, group in all_matches}
    updated_pairs = [
        (account_by_txn_id.get(group.primary.transaction_id, ""), group)
        for group in result.updated_transactions
    ]

    _persist_categorizations(
        updated_pairs,
        ready,
        workspace,
    )

    return 0


def _persist_categorizations(
    updated_pairs: list[tuple[str, TransactionGroup]],
    ready,
    workspace: Workspace,
) -> None:
    """Emit events, update CSVs, and rebuild projections for categorized transactions."""
    from gilt.services.categorization_persistence_service import CategorizationUpdate

    updates = [
        CategorizationUpdate(
            transaction_id=group.primary.transaction_id,
            account_id=account_id,
            category=group.primary.category or "",
            subcategory=group.primary.subcategory,
            source="user",
            confidence=1.0,
        )
        for account_id, group in updated_pairs
    ]
    apply_categorization_updates(ready, workspace, updates)


def _init_services(
    workspace: Workspace,
    service: TransactionOperationsService | None,
    categorization_service: CategorizationService | None,
) -> tuple[TransactionOperationsService, CategorizationService]:
    """Initialize services if not provided."""
    if service is None:
        service = TransactionOperationsService()

    category_config = load_categories_config(workspace.categories_config)

    event_store = load_event_store(workspace)

    if categorization_service is None:
        categorization_service = CategorizationService(
            category_config=category_config,
            transaction_service=service,
            event_store=event_store,
        )

    return service, categorization_service


def _read_batch_input(txid_file: Path | None, from_stdin: bool) -> str | int:
    """Read batch input from file or stdin. Returns text or exit-code int on error."""
    if txid_file is not None:
        if not txid_file.exists():
            print_error(f"Batch file not found: {txid_file}")
            return 1
        return txid_file.read_text(encoding="utf-8")
    # from_stdin
    return sys.stdin.read()


def _parse_batch_lines(text: str) -> tuple[list[tuple[int, str, str]], list[str]]:
    """Parse batch input text.

    Returns (entries, errors).
    Each entry is (line_no, txid_prefix, category_path).
    Lines starting with '#' or blank after stripping are skipped.
    Errors include the line number for malformed lines (fewer than two tokens).
    """
    entries: list[tuple[int, str, str]] = []
    errors: list[str] = []
    for line_no, raw_line in enumerate(text.splitlines(), start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split(None, 1)  # split on first whitespace, rest is category
        if len(parts) < 2:
            errors.append(
                f"Line {line_no}: malformed — expected '<txid> <category>', got: {line!r}"
            )
            continue
        txid_prefix, category_path = parts[0], parts[1].strip()
        entries.append((line_no, txid_prefix, category_path))
    return entries, errors


def _resolve_batch_entries(
    entries: list[tuple[int, str, str]],
    all_transactions: list[dict],
    account: str | None,
    categorization_service: CategorizationService,
    service: TransactionOperationsService,
) -> tuple[list[tuple[str, str, str, str | None]], list[str]]:
    """Resolve txid prefixes and validate categories for all batch entries.

    Returns (resolved, errors).
    Each resolved item is (transaction_id, account_id, category, subcategory).
    Errors include line numbers for any problem lines.
    """
    resolved: list[tuple[str, str, str, str | None]] = []
    errors: list[str] = []

    for line_no, txid_prefix, category_path in entries:
        # Validate category first
        cat_name, subcat_name, _ = parse_category_path(category_path)
        validation = categorization_service.validate_category(cat_name, subcat_name)
        if not validation.is_valid:
            errors.append(f"Line {line_no}: {'; '.join(validation.errors)}")
            continue

        # Resolve txid prefix
        result = service.find_projection_by_prefix(txid_prefix, all_transactions)
        if result.error is not None:
            if result.error == "prefix_too_short":
                msg = f"Transaction ID prefix must be at least 8 characters: '{txid_prefix}'"
            elif result.error == "not_found":
                msg = f"No transaction found for prefix '{txid_prefix}'"
            else:
                sample = ", ".join(result.ambiguous_matches or [])
                msg = f"Ambiguous prefix '{txid_prefix}' — matches multiple transactions ({sample})"
            errors.append(f"Line {line_no}: {msg}")
            continue

        txn = result.transaction
        resolved.append((txn["transaction_id"], txn["account_id"], cat_name, subcat_name))

    return resolved, errors


def _run_file_batch(
    workspace: Workspace,
    account: str | None,
    txid_file: Path | None,
    from_stdin: bool,
    write: bool,
    service: TransactionOperationsService | None,
    categorization_service: CategorizationService | None,
) -> int:
    """Orchestrate the file batch flow: read → parse → resolve → preview → persist."""
    text = _read_batch_input(txid_file, from_stdin)
    if isinstance(text, int):
        return text

    entries, parse_errors = _parse_batch_lines(text)
    if parse_errors:
        for err in parse_errors:
            print_error(err)
        return 1

    if not entries:
        console.print("[yellow]No entries found in batch input[/]")
        return 0

    all_transactions = load_account_transactions(workspace, account)
    if all_transactions is None:
        return 1

    svc, cat_svc = _init_services(workspace, service, categorization_service)

    resolved, resolve_errors = _resolve_batch_entries(
        entries, all_transactions, account, cat_svc, svc
    )
    if resolve_errors:
        for err in resolve_errors:
            print_error(err)
        return 1

    # Build (account_id, TransactionGroup) preview pairs from resolved entries
    txn_by_id = {row["transaction_id"]: row for row in all_transactions}
    preview_matches: list[tuple[str, TransactionGroup]] = []
    for txn_id, acct_id, cat, subcat in resolved:
        row = txn_by_id.get(txn_id)
        if row is None:
            continue
        group = TransactionGroup.from_projection_row(row)
        # Temporarily set target category on the group for display
        updated_txn = group.primary.model_copy(update={"category": cat, "subcategory": subcat})
        updated_group = TransactionGroup(
            group_id=group.group_id,
            primary=updated_txn,
            splits=group.splits,
        )
        preview_matches.append((acct_id, updated_group))

    _display_batch_preview(preview_matches, resolved)

    if not write:
        print_dry_run_message()
        return 0

    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1

    from gilt.services.categorization_persistence_service import CategorizationUpdate

    updates = [
        CategorizationUpdate(
            transaction_id=txn_id,
            account_id=acct_id,
            category=cat,
            subcategory=subcat,
            source="user",
            confidence=1.0,
        )
        for txn_id, acct_id, cat, subcat in resolved
    ]
    apply_categorization_updates(ready, workspace, updates)
    console.print(f"[green]✓[/] Categorized {len(updates)} transaction(s)")
    return 0


def _display_batch_preview(
    preview_matches: list[tuple[str, TransactionGroup]],
    resolved: list[tuple[str, str, str, str | None]],
) -> None:
    """Display a preview table for file-batch categorizations."""
    # Build a quick lookup: txn_id → (category, subcategory)
    cat_by_txn = {txn_id: (cat, subcat) for txn_id, _acct, cat, subcat in resolved}

    def row_fn(item: tuple[str, TransactionGroup]) -> tuple:
        account_id, group = item
        t = group.primary
        cat, subcat = cat_by_txn.get(t.transaction_id, (t.category or "", t.subcategory))
        new_cat = cat + (f":{subcat}" if subcat else "")
        return (
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:40],
            fmt_amount_str(t.amount),
            new_cat,
        )

    display_transaction_matches(
        "Batch Categorization Preview",
        [("→ Category", {"style": "green"})],
        preview_matches,
        row_fn,
    )


def run(
    *,
    account: str | None = None,
    txid: str | None = None,
    description: str | None = None,
    desc_prefix: str | None = None,
    pattern: str | None = None,
    amount: float | None = None,
    category: str | None = None,
    subcategory: str | None = None,
    assume_yes: bool = False,
    workspace: Workspace,
    write: bool = False,
    service: TransactionOperationsService | None = None,
    categorization_service: CategorizationService | None = None,
    txid_file: Path | None = None,
    from_stdin: bool = False,
) -> int:
    """Categorize transactions in ledger files.

    Modes:
    - Single: --txid to target one transaction
    - Batch: --description, --desc-prefix, or --pattern
      (optionally with --amount) to target multiple
    - File batch: --txid-file or --from-stdin to apply many txid→category mappings at once

    Category specification:
    - Use --category "Category" for category only
    - Use --category "Category" --subcategory "Subcategory" OR
    - Use --category "Category:Subcategory" (shorthand)

    Scope:
    - --account ACCOUNT: Categorize in one account
    - (no --account): Categorize across all accounts

    Safety: dry-run by default. Use --write to persist changes.

    Returns:
        Exit code (0 success, 1 error)
    """
    file_batch_mode = txid_file is not None or from_stdin

    if file_batch_mode:
        # Reject combinations of file-batch with single/batch flags
        if any(
            v is not None for v in [txid, description, desc_prefix, pattern, category, subcategory]
        ):
            print_error(
                "--txid-file / --from-stdin cannot be combined with "
                "--txid, --description, --desc-prefix, --pattern, --category, or --subcategory"
            )
            return 1
        return _run_file_batch(
            workspace=workspace,
            account=account,
            txid_file=txid_file,
            from_stdin=from_stdin,
            write=write,
            service=service,
            categorization_service=categorization_service,
        )

    # Standard single/batch mode — category is required
    if category is None:
        print_error(
            "--category is required (or use --txid-file / --from-stdin for file batch mode)"
        )
        return 1

    inputs = _validate_inputs(
        workspace,
        service,
        categorization_service,
        category,
        subcategory,
        txid,
        description,
        desc_prefix,
        pattern,
    )
    if isinstance(inputs, int):
        return inputs
    service, categorization_service, category, subcategory, single_mode = inputs

    all_transactions = load_account_transactions(workspace, account)
    if all_transactions is None:
        return 1

    all_matches = _resolve_targets(
        all_transactions, single_mode, txid, description, desc_prefix, pattern, amount, service
    )
    if all_matches is None:
        return 1

    if len(all_matches) == 0:
        console.print("[yellow]No matching transactions found[/]")
        return 0

    if single_mode and len(all_matches) > 1:
        console.print(
            f"[yellow]Ambiguous --txid '{txid}':[/] matches {len(all_matches)} transactions"
        )
        console.print("Refine with more characters or specify --account")
        return 1

    recategorized_count = sum(
        1 for _, g in all_matches if g.primary.category is not None and g.primary.category != ""
    )
    if not single_mode and len(all_matches) > 1 and not assume_yes and not write:
        console.print(
            f"[yellow]Batch mode:[/] {len(all_matches)} transactions would be categorized. "
            f"Use --yes to auto-confirm (dry-run)"
        )

    result = _confirm_and_apply(
        all_matches,
        category,
        subcategory,
        single_mode,
        assume_yes,
        write,
        workspace,
        categorization_service,
    )
    return _report_categorization_result(all_matches, result, recategorized_count, write)


def _validate_inputs(
    workspace: Workspace,
    service: TransactionOperationsService | None,
    categorization_service: CategorizationService | None,
    category: str,
    subcategory: str | None,
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
) -> tuple[TransactionOperationsService, CategorizationService, str, str | None, bool] | int:
    """Initialize services and validate inputs. Returns initialized tuple or exit code."""
    service, categorization_service = _init_services(workspace, service, categorization_service)
    category, subcategory, cat_warning = parse_category_path(category, subcategory)
    if cat_warning:
        console.print(f"[yellow]Warning:[/] {cat_warning}")

    mode_result = validate_single_vs_batch_mode(txid, description, desc_prefix, pattern)
    if mode_result is None:
        return 1
    single_mode = mode_result

    validation = categorization_service.validate_category(category, subcategory)
    if not validation.is_valid:
        for error in validation.errors:
            print_error(error)
        console.print(f"Add it first: gilt category --add '{category}' --write")
        return 1

    return service, categorization_service, category, subcategory, single_mode


def _report_categorization_result(
    all_matches: list[tuple[str, TransactionGroup]],
    result: int,
    recategorized_count: int,
    write: bool,
) -> int:
    """Report post-apply categorization success with recategorized-count warning. Returns exit code."""
    if result == 0 and write:
        if recategorized_count > 0:
            console.print(
                f"[yellow]Warning:[/] {recategorized_count} transaction(s) already had a category "
                f"and were re-categorized"
            )
        console.print(f"[green]✓[/] Categorized {len(all_matches)} transaction(s)")
    return result


def _display_matches(
    matches: list[tuple[str, TransactionGroup]],
    category: str,
    subcategory: str | None,
) -> None:
    """Display matched transactions in a table."""
    new_cat = category + (f":{subcategory}" if subcategory else "")

    def row_fn(item: tuple[str, TransactionGroup]) -> tuple:
        account_id, group = item
        t = group.primary
        current_cat = ""
        if t.category:
            current_cat = t.category
            if t.subcategory:
                current_cat += f":{t.subcategory}"
        return (
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:40],
            fmt_amount_str(t.amount),
            current_cat or "—",
            new_cat,
        )

    display_transaction_matches(
        "Matched Transactions",
        [("Current Cat", {"style": "dim"}), ("→ New Cat", {"style": "green"})],
        matches,
        row_fn,
    )


__all__ = ["run"]
