from __future__ import annotations

import logging
from pathlib import Path

import typer

from gilt.model.account import TransactionGroup
from gilt.model.category_io import load_categories_config, parse_category_path
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_service import CategorizationService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.services.transaction_operations_service import (
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.workspace import Workspace

from .util import (
    console,
    display_transaction_matches,
    filter_by_account,
    fmt_amount_str,
    print_dry_run_message,
    print_error,
    require_event_sourcing,
    require_persistence_service,
    require_projections,
    validate_single_vs_batch_mode,
)

"""Categorize transactions (single or batch mode)."""

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


def _parse_and_validate_category(category: str, subcategory: str | None) -> tuple[str, str | None, str | None]:
    """Parse 'Category:Subcategory' syntax and resolve conflicts. Returns (cat, subcat, warning)."""
    if ":" in category:
        cat_name, subcat_from_path = parse_category_path(category)
        warning = None
        if subcategory and subcategory != subcat_from_path:
            warning = (
                f"Both --category contains ':' and --subcategory specified. "
                f"Using category='{cat_name}', subcategory='{subcat_from_path}'"
            )
        return cat_name, subcat_from_path, warning
    return category, subcategory, None




def _load_and_filter_transactions(
    workspace: Workspace,
    account: str | None,
) -> list[dict] | None:
    """Load transactions from projections, filter by account. Returns None on error."""
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return None

    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    all_transactions = filter_by_account(all_transactions, account)
    if account and not all_transactions:
        print_error(f"No transactions found for account '{account}'")
        return None

    if not all_transactions:
        print_error("No transactions found in projections database")
        return None

    return all_transactions


def _find_matches(
    groups_by_account: dict[str, list[TransactionGroup]],
    single_mode: bool,
    txid: str | None,
    criteria: SearchCriteria,
    pattern: str | None,
    service: TransactionOperationsService,
) -> list[tuple[str, TransactionGroup]] | None:
    """Find matching transactions. Returns None on error (invalid pattern or ambiguous)."""
    all_matches: list[tuple[str, TransactionGroup]] = []

    for account_id, groups in groups_by_account.items():
        result = service.resolve_transaction_targets(
            groups,
            txid=txid if single_mode else None,
            description=criteria.description,
            desc_prefix=criteria.desc_prefix,
            pattern=criteria.pattern,
            amount=criteria.amount,
        )
        if isinstance(result, str):
            if result:
                print_error(result)
            return None
        for match in result:
            all_matches.append((account_id, match))

    return all_matches


def _group_by_account(transactions: list[dict]) -> dict[str, list[TransactionGroup]]:
    """Group projection rows into TransactionGroup lists keyed by account_id."""
    groups_by_account: dict[str, list[TransactionGroup]] = {}
    for row in transactions:
        account_id = row["account_id"]
        groups_by_account.setdefault(account_id, []).append(
            TransactionGroup.from_projection_row(row)
        )
    return groups_by_account


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
    groups_by_account = _group_by_account(all_transactions)
    return _find_matches(groups_by_account, single_mode, txid, criteria, pattern, service)


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

    result = categorization_service.apply_categorization(
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

    persistence_svc = require_persistence_service(ready, workspace)
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
    persistence_svc.persist_categorizations(updates)


def _init_services(
    workspace: Workspace,
    service: TransactionOperationsService | None,
    categorization_service: CategorizationService | None,
) -> tuple[TransactionOperationsService, CategorizationService]:
    """Initialize services if not provided."""
    if service is None:
        service = TransactionOperationsService()

    category_config = load_categories_config(workspace.categories_config)

    event_store = None
    if workspace.event_store_path.exists():
        event_store = EventSourcingService(workspace=workspace).get_event_store()

    if categorization_service is None:
        categorization_service = CategorizationService(
            category_config=category_config,
            transaction_service=service,
            event_store=event_store,
        )

    return service, categorization_service


def run(
    *,
    account: str | None = None,
    txid: str | None = None,
    description: str | None = None,
    desc_prefix: str | None = None,
    pattern: str | None = None,
    amount: float | None = None,
    category: str,
    subcategory: str | None = None,
    assume_yes: bool = False,
    workspace: Workspace,
    write: bool = False,
    service: TransactionOperationsService | None = None,
    categorization_service: CategorizationService | None = None,
) -> int:
    """Categorize transactions in ledger files.

    Modes:
    - Single: --txid to target one transaction
    - Batch: --description, --desc-prefix, or --pattern
      (optionally with --amount) to target multiple

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
    inputs = _validate_inputs(
        workspace, service, categorization_service, category, subcategory,
        txid, description, desc_prefix, pattern,
    )
    if isinstance(inputs, int):
        return inputs
    service, categorization_service, category, subcategory, single_mode = inputs

    all_transactions = _load_and_filter_transactions(workspace, account)
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
        all_matches, category, subcategory, single_mode, assume_yes, write,
        workspace, categorization_service,
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
    category, subcategory, cat_warning = _parse_and_validate_category(category, subcategory)
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
