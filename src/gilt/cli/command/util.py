from __future__ import annotations

import sys
from collections.abc import Callable, Iterable, Sequence
from pathlib import Path
from typing import Any

import typer
from rich.console import Console
from rich.table import Table
from rich.text import Text

from gilt.cli.presentation import build_transaction_table
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category_io import build_category_from_path, format_category_path
from gilt.model.ledger_repository import LedgerRepository
from gilt.services.categorization_persistence_service import (
    CategorizationPersistenceResult,
    CategorizationPersistenceService,
    CategorizationUpdate,
)
from gilt.services.event_sourcing_service import EventSourcingReadyResult, EventSourcingService
from gilt.services.transaction_operations_service import (
    BatchPreview,
    SearchCriteria,
    TransactionLookupResult,
    TransactionOperationsService,
)
from gilt.services.transaction_query_service import TransactionFilter, TransactionQueryService
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace

console = Console()


def print_error(message: str) -> None:
    console.print(f"[red]Error:[/] {message}")


def print_warning(message: str) -> None:
    console.print(f"[yellow]Warning:[/] {message}")


def print_error_list(heading: str, errors: list[str]) -> None:
    console.print(f"[red]{heading}:[/]")
    for error in errors:
        console.print(f"  • {error}")


def group_by_account(rows: list[dict]) -> dict[str, list[TransactionGroup]]:
    """Group projection rows into TransactionGroup lists keyed by account_id."""
    groups_by_account: dict[str, list[TransactionGroup]] = {}
    for row in rows:
        account_id = row["account_id"]
        groups_by_account.setdefault(account_id, []).append(
            TransactionGroup.from_projection_row(row)
        )
    return groups_by_account


def find_uncategorized(rows: list[dict]) -> list[dict]:
    return [row for row in rows if not row.get("category")]


def find_by_account(rows: list[dict], account: str | None) -> list[dict]:
    if account is None:
        return rows
    return [row for row in rows if row.get("account_id") == account]


def print_transaction_table(
    table: Table,
    total_count: int,
    *,
    display_limit: int = 50,
) -> None:
    """Print a transaction table and an overflow message if total_count exceeds display_limit.

    Args:
        table: The Rich Table to print.
        total_count: The true number of transactions (before any slice was applied).
        display_limit: Maximum rows shown before the overflow message is printed.
    """
    console.print(table)
    if total_count > display_limit:
        console.print(f"[dim]... and {total_count - display_limit} more[/]")


def load_ledger_text(ledger_path: Path) -> str:
    if not ledger_path.exists():
        raise FileNotFoundError(f"Ledger file not found: {ledger_path}")
    return ledger_path.read_text(encoding="utf-8")


def fmt_amount(amt: float) -> Text:
    s = f"{amt:,.2f}"
    if amt < 0:
        return Text(s, style="bold red")
    elif amt > 0:
        return Text(s, style="bold green")
    return Text(s)


def fmt_amount_str(amt: float, *, prefix: str = "$") -> str:
    """Format an amount as a plain string with dollar sign and thousands separator."""
    return f"{prefix}{amt:,.2f}"


def fmt_colored_amount(amt: float, *, prefix: str = "$", bold: bool = False) -> str:
    """Format an amount as a Rich markup string with sign-based color (red/green)."""
    s = fmt_amount_str(amt, prefix=prefix)
    weight = " bold" if bold else ""
    if amt < 0:
        return f"[red{weight}]{s}[/]"
    elif amt > 0:
        return f"[green{weight}]{s}[/]"
    return f"[bold]{s}[/]" if bold else s


def format_prefix_lookup_error(result: TransactionLookupResult, prefix: str) -> str:
    """Format a TransactionLookupResult error into a human-readable message."""
    if result.error == "prefix_too_short":
        return f"Transaction ID prefix must be at least 8 characters: '{prefix}'"
    elif result.error == "not_found":
        return f"No transaction found matching ID prefix '{prefix}'"
    else:
        sample = ", ".join(result.ambiguous_matches or [])
        return f"Ambiguous prefix '{prefix}': matches multiple transactions ({sample})"


def confirm_interactively(prompt: str) -> bool:
    """Return True when stdin is non-interactive (auto-proceed) or when the user confirms."""
    if not sys.stdin.isatty():
        return True
    return typer.confirm(prompt)


def persist_categorization_matches(
    matches: list[tuple[str, TransactionGroup]],
    category: str,
    subcategory: str | None,
    ready: EventSourcingReadyResult,
    workspace: Workspace,
    *,
    source: str,
) -> int:
    """Build and apply categorization updates for a list of (account_id, group) matches."""
    updates = build_categorization_updates(
        (
            (g.primary.transaction_id, acct, category, subcategory, 1.0)
            for acct, g in matches
        ),
        source=source,
    )
    result = run_categorization_updates(ready, workspace, updates)
    return result.transactions_updated


def base_match_row(account_id: str, t: Transaction) -> tuple:
    """Build the 5-column base row used by match-display functions."""
    return (
        account_id,
        t.transaction_id[:8],
        str(t.date),
        (t.description or "")[:40],
        fmt_amount_str(t.amount),
    )


def print_dry_run_message(*, detail: str | None = None) -> None:
    """Print the standard dry-run warning. Call when write=False."""
    if detail:
        msg = f"Dry-run: use --write to persist {detail}"
    else:
        msg = "Dry-run: use --write to persist changes"
    console.print(f"[dim]{msg}[/dim]")


def build_effective_paths(
    workspace: Workspace,
    event_store_path: Path | None,
    projections_db_path: Path | None,
    budget_projections_db_path: Path | None,
) -> tuple[Path, Path, Path]:
    """Resolve effective paths for event store and projections, falling back to workspace defaults."""
    return (
        event_store_path or workspace.event_store_path,
        projections_db_path or workspace.projections_path,
        budget_projections_db_path or workspace.budget_projections_path,
    )


def build_event_sourcing_service(
    workspace: Workspace,
    event_store_path: Path | None = None,
    projections_path: Path | None = None,
) -> EventSourcingService:
    """Construct an EventSourcingService with optional path overrides."""
    return EventSourcingService(
        event_store_path=event_store_path,
        projections_path=projections_path,
        workspace=workspace,
    )


def require_event_sourcing(
    workspace: Workspace,
    *,
    event_store_path: Path | None = None,
    projections_path: Path | None = None,
) -> EventSourcingReadyResult | None:
    """Initialize event sourcing or print error and return None.

    Calls ensure_ready() which auto-rebuilds projections if needed.
    Uses the error message pattern from the duplicates command (most informative).

    Args:
        workspace: Workspace for resolving default paths.
        event_store_path: Override the event store DB path. Defaults to workspace path.
        projections_path: Override the projections DB path. Defaults to workspace path.
    """
    data_dir = workspace.ledger_data_dir
    es_service = build_event_sourcing_service(workspace, event_store_path, projections_path)
    result = es_service.ensure_ready(data_dir=data_dir if data_dir.exists() else None)

    if not result.ready:
        if result.error == "no_event_store":
            console.print(
                f"[yellow]Event store not found, but found {result.csv_files_count} CSV file(s)[/]"
            )
            console.print()
            console.print("[bold]To migrate your existing data to event sourcing:[/]")
            console.print("  gilt migrate-to-events --write")
            console.print()
            console.print(
                "[dim]This will create the event store and projections from your CSV files.[/dim]"
            )
        elif data_dir.exists():
            console.print(f"[red]Error:[/red] No data found in {data_dir}")
            console.print()
            console.print("[bold]To get started:[/]")
            console.print("  1. Export CSV files from your bank")
            console.print("  2. Place them in ingest/ directory")
            console.print("  3. Run: gilt ingest --write")
        else:
            console.print(f"[red]Error:[/red] Data directory not found: {data_dir}")
        return None

    if result.events_processed > 0:
        console.print(
            f"[green]✓[/green] Projections rebuilt ({result.events_processed} events processed)"
        )
        console.print()

    return result


def require_persistence_service(
    ready: EventSourcingReadyResult,
    workspace: Workspace,
) -> CategorizationPersistenceService:
    """Construct a CategorizationPersistenceService from components."""
    return CategorizationPersistenceService(
        event_store=ready.event_store,
        projection_builder=ready.projection_builder,
        ledger_repo=LedgerRepository(workspace.ledger_data_dir),
    )


def load_account_transactions(workspace: Workspace, account: str | None) -> list[dict] | None:
    """require_projections → get_all_transactions(include_duplicates=False) → find_by_account.

    Prints an error and returns None when projections are missing or when no transactions
    exist for the requested account.
    """
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return None

    all_transactions = projection_builder.get_all_transactions(include_duplicates=False)
    all_transactions = find_by_account(all_transactions, account)

    if account and not all_transactions:
        print_error(f"No transactions found for account '{account}'")
        return None

    if not all_transactions:
        print_error("No transactions found in projections database")
        return None

    return all_transactions


def load_all_transactions(
    workspace: Workspace,
    *,
    include_duplicates: bool,
) -> list[Transaction] | None:
    """require_projections → get_all_transactions → convert to Transaction objects.

    Returns None when projections are missing.
    """
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return None

    rows = projection_builder.get_all_transactions(include_duplicates=include_duplicates)
    return [Transaction.from_projection_row(row) for row in rows]


def run_categorization_updates(
    ready: EventSourcingReadyResult,
    workspace: Workspace,
    updates: list,
) -> CategorizationPersistenceResult:
    """Construct persistence service and forward updates to persist_categorizations."""
    return require_persistence_service(ready, workspace).persist_categorizations(updates)


def build_categorization_updates(
    rows: Iterable[tuple[str, str, str, str | None, float]],
    *,
    source: str,
) -> list[CategorizationUpdate]:
    """Build CategorizationUpdate objects from (transaction_id, account_id, category, subcategory, confidence) tuples."""
    return [
        CategorizationUpdate(
            transaction_id=transaction_id,
            account_id=account_id,
            category=category,
            subcategory=subcategory,
            source=source,
            confidence=confidence,
        )
        for transaction_id, account_id, category, subcategory, confidence in rows
    ]


def load_event_store(workspace: Workspace) -> EventStore | None:
    """Return the event store if it exists, else None (read-only access)."""
    if workspace.event_store_path.exists():
        return build_event_sourcing_service(workspace).get_event_store()
    return None


def build_category_path(
    category: str,
    subcategory: str | None = None,
) -> tuple[str, str | None, str | None]:
    """Split 'Category:Subcategory' syntax and resolve --subcategory conflicts.

    Returns (cat_name, subcat_name, warning).
    cat_name is empty string when the input has no valid category part.
    warning is a non-None string when --subcategory conflicts with the ':' syntax.
    """
    cat_name, subcat_from_path = build_category_from_path(category)
    if not cat_name:
        return "", None, None

    if ":" in category and subcategory and subcategory != subcat_from_path:
        warning = (
            f"Both --category contains ':' and --subcategory specified. "
            f"Using category='{cat_name}', subcategory='{subcat_from_path}'"
        )
        return cat_name, subcat_from_path, warning

    if ":" in category:
        return cat_name, subcat_from_path, None

    return cat_name, subcategory, None


def display_transaction_matches(
    title: str,
    extra_columns: list[tuple[str, dict]],
    matches: Sequence,
    row_fn: Callable[[Any], tuple],
    *,
    display_limit: int = 50,
) -> None:
    """Create and print a transaction table for a sequence of matches.

    Args:
        title: Table title passed to ``build_transaction_table``.
        extra_columns: Extra column specs passed to ``build_transaction_table``.
        matches: The full sequence of matches. Only the first ``display_limit`` are rendered.
        row_fn: Callable that accepts a single match item and returns a tuple of column values
            matching (account, txn_id_prefix, date, description, amount, *extra_values).
        display_limit: Maximum rows to render before the overflow message is shown.
    """
    table = build_transaction_table(title, extra_columns)
    for item in matches[:display_limit]:
        table.add_row(*row_fn(item))
    print_transaction_table(table, len(matches), display_limit=display_limit)


def display_category_change_matches(
    title: str,
    from_header: str,
    to_header: str,
    matches: Sequence[tuple[str, TransactionGroup]],
    to_label: str,
    *,
    from_label: str | None = None,
) -> None:
    """Create and print a category-change transaction table.

    Each row shows the standard transaction columns plus a from-category column
    and a to-category column.  When ``from_label`` is supplied every row shows
    that fixed label in the from column; when it is ``None`` each row shows the
    transaction's current ``category:subcategory`` (or ``"—"`` when empty).

    Args:
        title: Table title.
        from_header: Column header for the "from" category column.
        to_header: Column header for the "to" category column.
        matches: Sequence of ``(account_id, TransactionGroup)`` pairs.
        to_label: Fixed label shown in the to column for every row.
        from_label: When supplied, shown as-is in the from column for every row.
    """

    def row_fn(item: tuple[str, TransactionGroup]) -> tuple:
        account_id, group = item
        t = group.primary
        if from_label is not None:
            from_col = from_label
        else:
            from_col = format_category_path(t.category or "", t.subcategory) or "—"
        return base_match_row(account_id, t) + (from_col, to_label)

    display_transaction_matches(
        title,
        [(from_header, {"style": "dim"}), (to_header, {"style": "green"})],
        matches,
        row_fn,
    )


def require_projections(workspace: Workspace) -> ProjectionBuilder | None:
    """Load projections or print error and return None."""
    if not workspace.projections_path.exists():
        console.print(
            f"[red]Error:[/red] Projections database not found at {workspace.projections_path}\n"
            "[dim]Run 'gilt rebuild-projections' first[/dim]"
        )
        return None
    return ProjectionBuilder(workspace.projections_path)


def load_filtered_transactions(
    workspace: Workspace,
    criteria: TransactionFilter,
    *,
    include_duplicates: bool = False,
) -> list[Transaction] | None:
    """Load all transactions from projections and filter by the given criteria.

    Returns None when the projections database is missing or unavailable.
    Returns an empty list when there are no matching transactions.

    Args:
        workspace: Workspace providing the projections database path.
        criteria: Filter criteria applied via TransactionQueryService.find_matching.
        include_duplicates: When True, duplicate transactions are included in the load.

    Returns:
        Filtered Transaction list, or None if projections are unavailable.
    """
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return None
    rows = projection_builder.get_all_transactions(include_duplicates=include_duplicates)
    transactions = [Transaction.from_projection_row(row) for row in rows]
    return TransactionQueryService().find_matching(transactions, criteria)


def validate_single_vs_batch_mode(
    txid: str | None,
    description: str | None,
    desc_prefix: str | None,
    pattern: str | None,
) -> bool | None:
    """Validate exactly one of txid/description/desc_prefix/pattern is specified.

    Returns True if single mode (txid), False if batch mode, or None on error.
    Prints an error message when no mode or multiple modes are specified.
    """
    single_mode = bool((txid or "").strip())
    modes_selected = sum(
        [single_mode, description is not None, desc_prefix is not None, pattern is not None]
    )
    if modes_selected != 1:
        print_error("Specify exactly one of --txid, --description, --desc-prefix, or --pattern")
        return None
    return single_mode


def find_by_id_prefix(
    service: TransactionOperationsService,
    prefix: str,
    groups: list[TransactionGroup],
) -> list[TransactionGroup] | str:
    """Find transactions by ID prefix with validation and formatted error messages.

    Validates the prefix is at least 8 characters, calls find_by_id_prefix,
    and returns either the matched groups or an error string describing the problem.

    Args:
        service: Service used to perform the lookup.
        prefix: Transaction ID prefix to look up.
        groups: Transaction groups to search within.

    Returns:
        A list of matching TransactionGroup objects on success, or a non-empty
        error string describing the problem (not_found or ambiguous).
    """
    normalized = prefix.strip().lower()
    if len(normalized) < 8:
        return f"Transaction ID prefix must be at least 8 characters. Got: {len(normalized)}"

    result = service.find_by_id_prefix(normalized, groups)

    if result.type == "not_found":
        return f"No transaction found matching ID prefix '{normalized}'"

    if result.type == "ambiguous":
        sample = []
        for g in (result.matches or [])[:5]:
            t = g.primary
            sample.append(
                f"{t.date} id={t.transaction_id[:8]} amt={t.amount} desc='{(t.description or '').strip()}'"
            )
        detail = (" Examples: " + "; ".join(sample)) if sample else ""
        return (
            f"Ambiguous prefix '{normalized}': matches {len(result.matches or [])} transactions."
            + detail
        )

    return [result.transaction] if result.transaction else []


def find_matches_by_criteria(
    groups_by_account: dict[str, list[TransactionGroup]],
    criteria: SearchCriteria,
    service: TransactionOperationsService,
    *,
    txid: str | None = None,
) -> list[tuple[str, TransactionGroup]] | None:
    all_matches: list[tuple[str, TransactionGroup]] = []
    for account_id, groups in groups_by_account.items():
        result = service.find_transaction_targets(
            groups,
            txid=txid,
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


def run_confirmed_mutation(
    *,
    matches: Sequence,
    display: Callable[[], None],
    confirm_prompt: str,
    assume_yes: bool,
    write: bool,
    apply: Callable[[], int],
) -> int:
    """Orchestrate the confirm → dry-run gate → apply mutation sequence."""
    display()
    if not assume_yes and not confirm_interactively(confirm_prompt):
        console.print("Cancelled")
        return 0
    if not write:
        print_dry_run_message()
        return 0
    return apply()


def search_by_criteria(
    service: TransactionOperationsService,
    criteria: SearchCriteria,
    groups: list[TransactionGroup],
    pattern: str | None,
) -> BatchPreview | None:
    """Search for transactions by criteria, printing warnings and errors as needed.

    Calls find_by_criteria on the service. If the pattern is invalid, prints an error
    and returns None. If sign-insensitive matching was used, prints a note.

    Args:
        service: Service used to perform the search.
        criteria: Search criteria (description, desc_prefix, pattern, amount).
        groups: Transaction groups to search within.
        pattern: The raw pattern string (used only in the error message).

    Returns:
        A BatchPreview on success, or None if the pattern was invalid.
    """
    preview = service.find_by_criteria(criteria, groups)

    if preview.invalid_pattern:
        print_error(f"Invalid regex pattern: {pattern}")
        return None

    if preview.used_sign_insensitive:
        console.print(
            "[yellow]Note:[/] matched by absolute amount "
            "since no signed matches were found. "
            "Ledger stores debits as negative amounts."
        )

    return preview
