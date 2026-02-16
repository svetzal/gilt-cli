from __future__ import annotations

from pathlib import Path
from typing import List, Optional
from datetime import datetime

import typer
from rich.table import Table

from .util import console
from gilt.workspace import Workspace
from gilt.model.category_io import load_categories_config, parse_category_path
from gilt.model.ledger_io import dump_ledger_csv, load_ledger_csv
from gilt.model.account import TransactionGroup, Transaction
from gilt.services.transaction_operations_service import (
    TransactionOperationsService,
    SearchCriteria,
)
from gilt.services.categorization_service import CategorizationService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.projection import ProjectionBuilder
from gilt.storage.event_store import EventStore
from gilt.model.events import TransactionCategorized


"""Categorize transactions (single or batch mode)."""


def _find_account_ledgers(data_dir: Path, account: Optional[str]) -> List[Path]:
    """Find ledger files to process."""
    if account:
        ledger_path = data_dir / f"{account}.csv"
        if not ledger_path.exists():
            return []
        return [ledger_path]
    else:
        # All accounts
        return sorted(data_dir.glob("*.csv"))


def run(
    *,
    account: Optional[str] = None,
    txid: Optional[str] = None,
    description: Optional[str] = None,
    desc_prefix: Optional[str] = None,
    pattern: Optional[str] = None,
    amount: Optional[float] = None,
    category: str,
    subcategory: Optional[str] = None,
    assume_yes: bool = False,
    workspace: Workspace,
    write: bool = False,
    service: Optional[TransactionOperationsService] = None,
    categorization_service: Optional[CategorizationService] = None,
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
    # Initialize services if not provided (for testing)
    if service is None:
        service = TransactionOperationsService()

    # Load category config
    category_config = load_categories_config(workspace.categories_config)

    # Initialize event store for tracking categorizations (if available)
    event_store = None
    try:
        event_sourcing_service = EventSourcingService(workspace=workspace)
        event_store_status = event_sourcing_service.check_event_store_status()
        if event_store_status.exists:
            event_store = event_sourcing_service.get_event_store()
    except Exception:
        # Event store not available - continue without event tracking
        pass

    if categorization_service is None:
        categorization_service = CategorizationService(
            category_config=category_config,
            transaction_service=service,
            event_store=event_store,
        )
    # Parse category path (supports "Category:Subcategory" syntax)
    if ":" in category:
        cat_name, subcat_from_path = parse_category_path(category)
        if subcategory and subcategory != subcat_from_path:
            console.print(
                f"[yellow]Warning:[/] Both --category contains ':' and --subcategory specified. "
                f"Using category='{cat_name}', subcategory='{subcat_from_path}'"
            )
        subcategory = subcat_from_path
        category = cat_name

    # Validate mode selection
    single_mode = bool((txid or "").strip())
    batch_exact_mode = description is not None
    batch_prefix_mode = desc_prefix is not None
    batch_pattern_mode = pattern is not None

    modes_selected = sum([single_mode, batch_exact_mode, batch_prefix_mode, batch_pattern_mode])
    if modes_selected != 1:
        console.print(
            "[red]Error:[/] Specify exactly one of --txid, "
            "--description, --desc-prefix, or --pattern"
        )
        return 1

    # Build search criteria for service
    criteria = SearchCriteria(
        description=description,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount=amount,
    )

    # Validate category exists using service
    validation = categorization_service.validate_category(category, subcategory)
    if not validation.is_valid:
        for error in validation.errors:
            console.print(f"[red]Error:[/red] {error}")
        console.print(f"Add it first: gilt category --add '{category}' --write")
        return 1

    # Check projections database exists
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found at {workspace.projections_path}\n"
            "[dim]Run 'gilt rebuild-projections' first[/dim]"
        )
        return 1

    # Load transactions from projections (excludes duplicates)
    projection_builder = ProjectionBuilder(workspace.projections_path)
    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)

    # Filter by account if specified
    if account:
        all_transactions = [row for row in all_transactions if row["account_id"] == account]
        if not all_transactions:
            console.print(f"[red]Error:[/] No transactions found for account '{account}'")
            return 1

    if not all_transactions:
        console.print("[red]Error:[/] No transactions found in projections database")
        return 1

    # Convert projection rows to TransactionGroup objects for service operations
    # Group by account_id to maintain mapping for CSV writes
    groups_by_account: dict[str, List[TransactionGroup]] = {}
    for row in all_transactions:
        account_id = row["account_id"]
        if account_id not in groups_by_account:
            groups_by_account[account_id] = []

        # Convert row dict to Transaction object
        txn = Transaction(
            transaction_id=row["transaction_id"],
            date=datetime.fromisoformat(row["transaction_date"]).date(),
            description=row["canonical_description"],
            amount=float(row["amount"]),
            currency=row["currency"],
            account_id=row["account_id"],
            counterparty=row.get("counterparty"),
            category=row.get("category"),
            subcategory=row.get("subcategory"),
            notes=row.get("notes"),
        )
        group = TransactionGroup(group_id=row["transaction_id"], primary=txn)
        groups_by_account[account_id].append(group)

    # Process groups using service for finding matches
    total_matched = 0
    all_matches: List[tuple[str, TransactionGroup]] = []  # (account_id, group)

    for account_id, groups in groups_by_account.items():
        # Use service for finding matches
        if single_mode:
            # Single mode: find by ID prefix
            result = service.find_by_id_prefix(txid or "", groups)
            if result.is_match and result.transaction:
                all_matches.append((account_id, result.transaction))
                total_matched += 1
            elif result.is_ambiguous and result.matches:
                # Add all ambiguous matches for error reporting
                for match in result.matches:
                    all_matches.append((account_id, match))
                    total_matched += 1
        else:
            # Batch mode: find by criteria
            preview = service.find_by_criteria(criteria, groups)

            # Check for invalid regex pattern
            if preview.invalid_pattern:
                console.print(f"[red]Invalid regex pattern:[/] {pattern}")
                return 1

            # Show warning if used sign-insensitive matching
            if preview.used_sign_insensitive:
                console.print(
                    "[yellow]Note:[/] matched by absolute amount "
                    "since no signed matches were found. "
                    "Ledger stores debits as negative amounts."
                )

            for match in preview.matched_groups:
                all_matches.append((account_id, match))
                total_matched += 1

    if total_matched == 0:
        console.print("[yellow]No matching transactions found[/]")
        return 0

    # Single mode: check for ambiguity
    if single_mode and total_matched > 1:
        console.print(f"[yellow]Ambiguous --txid '{txid}':[/] matches {total_matched} transactions")
        console.print("Refine with more characters or specify --account")
        return 1

    # Show what will be categorized
    _display_matches(all_matches, category, subcategory)

    # Check for re-categorization
    recategorized_count = sum(
        1 for _, g in all_matches if g.primary.category is not None and g.primary.category != ""
    )

    if recategorized_count > 0:
        console.print(
            f"[yellow]Warning:[/] {recategorized_count} transaction(s) already have a category "
            f"and will be re-categorized"
        )

    # Batch mode: require confirmation
    if not single_mode and total_matched > 1 and not assume_yes:
        if not write:
            console.print(
                f"[yellow]Batch mode:[/] {total_matched} transactions would be categorized. "
                f"Use --yes to auto-confirm (dry-run)"
            )
        else:
            import sys

            # Only prompt if in an interactive terminal
            if sys.stdin.isatty():
                if not typer.confirm(f"Categorize {total_matched} transaction(s)?"):
                    console.print("Cancelled")
                    return 0
            # Non-interactive environment (e.g., tests): proceed without prompting

    if not write:
        console.print("[dim]Dry-run: use --write to persist changes[/]")
        return 0

    # Apply categorization using service
    result = categorization_service.apply_categorization(
        [group for _, group in all_matches],
        category,
        subcategory,
    )

    # Write back to ledger files by account
    # Group by account_id and load CSV, apply updates, write back
    by_account: dict[str, List[tuple[str, TransactionGroup]]] = {}
    for account_id, group in all_matches:
        if account_id not in by_account:
            by_account[account_id] = []
        by_account[account_id].append((group.primary.transaction_id, group))

    # Map updated transactions by ID for lookup
    updated_by_id = {g.primary.transaction_id: g for g in result.updated_transactions}

    for account_id, items in by_account.items():
        ledger_path = workspace.ledger_data_dir / f"{account_id}.csv"
        if not ledger_path.exists():
            console.print(f"[yellow]Warning: Ledger not found for {account_id}[/yellow]")
            continue

        # Reload full ledger from CSV
        text = ledger_path.read_text(encoding="utf-8")
        groups = load_ledger_csv(text, default_currency="CAD")

        # Apply updates to matched transactions
        for i, g in enumerate(groups):
            if g.primary.transaction_id in updated_by_id:
                groups[i] = updated_by_id[g.primary.transaction_id]

        # Write back
        updated_csv = dump_ledger_csv(groups)
        ledger_path.write_text(updated_csv, encoding="utf-8")

    # Emit TransactionCategorized events and rebuild projections
    event_store = EventStore(workspace.event_store_path)
    projection_builder = ProjectionBuilder(workspace.projections_path)

    for group in result.updated_transactions:
        event = TransactionCategorized(
            transaction_id=group.primary.transaction_id,
            category=group.primary.category or "",
            subcategory=group.primary.subcategory,
            source="user",  # Manual categorization by user
            event_timestamp=datetime.now(),
        )
        event_store.append_event(event)

    # Rebuild projections incrementally to include new categorization events
    projection_builder.rebuild_incremental(event_store)

    console.print(f"[green]✓[/] Categorized {total_matched} transaction(s)")
    return 0


def _display_matches(
    matches: List[tuple[str, TransactionGroup]],
    category: str,
    subcategory: Optional[str],
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
