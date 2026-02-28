from __future__ import annotations

from datetime import datetime
from pathlib import Path

import typer
from rich.table import Table

from gilt.model.account import TransactionGroup
from gilt.model.category_io import load_categories_config, parse_category_path
from gilt.model.events import TransactionCategorized
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv
from gilt.services.categorization_service import CategorizationService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.services.transaction_operations_service import (
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

from .util import console

"""Categorize transactions (single or batch mode)."""


def _find_account_ledgers(data_dir: Path, account: str | None) -> list[Path]:
    """Find ledger files to process."""
    if account:
        ledger_path = data_dir / f"{account}.csv"
        if not ledger_path.exists():
            return []
        return [ledger_path]
    else:
        # All accounts
        return sorted(data_dir.glob("*.csv"))


def _parse_and_validate_category(category: str, subcategory: str | None) -> tuple[str, str | None]:
    """Parse 'Category:Subcategory' syntax and resolve conflicts."""
    if ":" in category:
        cat_name, subcat_from_path = parse_category_path(category)
        if subcategory and subcategory != subcat_from_path:
            console.print(
                f"[yellow]Warning:[/] Both --category contains ':' and --subcategory specified. "
                f"Using category='{cat_name}', subcategory='{subcat_from_path}'"
            )
        return cat_name, subcat_from_path
    return category, subcategory


def _validate_mode_selection(
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
) -> tuple[bool, bool] | None:
    """Validate exactly one mode is selected. Returns (single_mode, ok) or None on error."""
    single_mode = bool((txid or "").strip())
    modes_selected = sum([single_mode, description is not None, desc_prefix is not None, pattern is not None])
    if modes_selected != 1:
        console.print(
            "[red]Error:[/] Specify exactly one of --txid, "
            "--description, --desc-prefix, or --pattern"
        )
        return None
    return single_mode


def _load_and_filter_transactions(
    workspace: Workspace,
    account: str | None,
) -> list[dict] | None:
    """Load transactions from projections, filter by account. Returns None on error."""
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found at {workspace.projections_path}\n"
            "[dim]Run 'gilt rebuild-projections' first[/dim]"
        )
        return None

    projection_builder = ProjectionBuilder(workspace.projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    if account:
        all_transactions = [row for row in all_transactions if row["account_id"] == account]
        if not all_transactions:
            console.print(f"[red]Error:[/] No transactions found for account '{account}'")
            return None

    if not all_transactions:
        console.print("[red]Error:[/] No transactions found in projections database")
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
    """Find matching transactions. Returns None on error (invalid pattern)."""
    all_matches: list[tuple[str, TransactionGroup]] = []

    for account_id, groups in groups_by_account.items():
        if single_mode:
            result = service.find_by_id_prefix(txid or "", groups)
            if result.is_match and result.transaction:
                all_matches.append((account_id, result.transaction))
            elif result.is_ambiguous and result.matches:
                for match in result.matches:
                    all_matches.append((account_id, match))
        else:
            preview = service.find_by_criteria(criteria, groups)

            if preview.invalid_pattern:
                console.print(f"[red]Invalid regex pattern:[/] {pattern}")
                return None

            if preview.used_sign_insensitive:
                console.print(
                    "[yellow]Note:[/] matched by absolute amount "
                    "since no signed matches were found. "
                    "Ledger stores debits as negative amounts."
                )

            for match in preview.matched_groups:
                all_matches.append((account_id, match))

    return all_matches


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

    recategorized_count = sum(
        1 for _, g in all_matches if g.primary.category is not None and g.primary.category != ""
    )
    if recategorized_count > 0:
        console.print(
            f"[yellow]Warning:[/] {recategorized_count} transaction(s) already have a category "
            f"and will be re-categorized"
        )

    if not single_mode and total_matched > 1 and not assume_yes:
        if not write:
            console.print(
                f"[yellow]Batch mode:[/] {total_matched} transactions would be categorized. "
                f"Use --yes to auto-confirm (dry-run)"
            )
        else:
            import sys

            if sys.stdin.isatty() and not typer.confirm(
                f"Categorize {total_matched} transaction(s)?"
            ):
                console.print("Cancelled")
                return 0

    if not write:
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0

    result = categorization_service.apply_categorization(
        [group for _, group in all_matches],
        category,
        subcategory,
    )

    _write_back_ledgers(all_matches, result.updated_transactions, workspace)
    _emit_events_and_rebuild(result.updated_transactions, workspace)

    console.print(f"[green]✓[/] Categorized {total_matched} transaction(s)")
    return 0


def _write_back_ledgers(
    all_matches: list[tuple[str, TransactionGroup]],
    updated_transactions: list[TransactionGroup],
    workspace: Workspace,
) -> None:
    """Write updated transactions back to per-account ledger CSV files."""
    by_account: dict[str, list[str]] = {}
    for account_id, group in all_matches:
        by_account.setdefault(account_id, []).append(group.primary.transaction_id)

    updated_by_id = {g.primary.transaction_id: g for g in updated_transactions}

    for account_id in by_account:
        ledger_path = workspace.ledger_data_dir / f"{account_id}.csv"
        if not ledger_path.exists():
            console.print(f"[yellow]Warning: Ledger not found for {account_id}[/yellow]")
            continue

        text = ledger_path.read_text(encoding="utf-8")
        groups = load_ledger_csv(text, default_currency="CAD")

        for i, g in enumerate(groups):
            if g.primary.transaction_id in updated_by_id:
                groups[i] = updated_by_id[g.primary.transaction_id]

        updated_csv = dump_ledger_csv(groups)
        ledger_path.write_text(updated_csv, encoding="utf-8")


def _emit_events_and_rebuild(
    updated_transactions: list[TransactionGroup],
    workspace: Workspace,
) -> None:
    """Emit TransactionCategorized events and rebuild projections."""
    event_store = EventStore(workspace.event_store_path)
    projection_builder = ProjectionBuilder(workspace.projections_path)

    for group in updated_transactions:
        event = TransactionCategorized(
            transaction_id=group.primary.transaction_id,
            category=group.primary.category or "",
            subcategory=group.primary.subcategory,
            source="user",
            event_timestamp=datetime.now(),
        )
        event_store.append_event(event)

    projection_builder.rebuild_incremental(event_store)


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
    try:
        event_sourcing_service = EventSourcingService(workspace=workspace)
        event_store_status = event_sourcing_service.check_event_store_status()
        if event_store_status.exists:
            event_store = event_sourcing_service.get_event_store()
    except Exception:
        pass

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
    service, categorization_service = _init_services(
        workspace, service, categorization_service,
    )

    category, subcategory = _parse_and_validate_category(category, subcategory)

    mode_result = _validate_mode_selection(txid, description, desc_prefix, pattern)
    if mode_result is None:
        return 1
    single_mode = mode_result

    criteria = SearchCriteria(
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
    )

    validation = categorization_service.validate_category(category, subcategory)
    if not validation.is_valid:
        for error in validation.errors:
            console.print(f"[red]Error:[/red] {error}")
        console.print(f"Add it first: gilt category --add '{category}' --write")
        return 1

    all_transactions = _load_and_filter_transactions(workspace, account)
    if all_transactions is None:
        return 1

    groups_by_account: dict[str, list[TransactionGroup]] = {}
    for row in all_transactions:
        account_id = row["account_id"]
        groups_by_account.setdefault(account_id, []).append(
            TransactionGroup.from_projection_row(row)
        )

    all_matches = _find_matches(groups_by_account, single_mode, txid, criteria, pattern, service)
    if all_matches is None:
        return 1

    if len(all_matches) == 0:
        console.print("[yellow]No matching transactions found[/]")
        return 0

    if single_mode and len(all_matches) > 1:
        console.print(f"[yellow]Ambiguous --txid '{txid}':[/] matches {len(all_matches)} transactions")
        console.print("Refine with more characters or specify --account")
        return 1

    return _confirm_and_apply(
        all_matches, category, subcategory, single_mode, assume_yes, write,
        workspace, categorization_service,
    )


def _display_matches(
    matches: list[tuple[str, TransactionGroup]],
    category: str,
    subcategory: str | None,
) -> None:
    """Display matched transactions in a table."""
    table = Table(title="Matched Transactions", show_lines=False)
    table.add_column("Account", style="cyan", no_wrap=True)
    table.add_column("TxnID", style="blue", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Current Cat", style="dim")
    table.add_column("→ New Cat", style="green")

    for account_id, group in matches[:50]:  # Limit display to 50
        t = group.primary

        current_cat = ""
        if t.category:
            current_cat = t.category
            if t.subcategory:
                current_cat += f":{t.subcategory}"

        new_cat = category
        if subcategory:
            new_cat += f":{subcategory}"

        table.add_row(
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:40],
            f"${t.amount:,.2f}",
            current_cat or "—",
            new_cat,
        )

    console.print(table)

    if len(matches) > 50:
        console.print(f"[dim]... and {len(matches) - 50} more[/]")


__all__ = ["run"]
