from __future__ import annotations

"""
Rename categories or recategorize a filtered selection of transactions.

Two operating modes:

  1. **Rename mode** (--from required, no selection flags):
     Renames every transaction with the given category/subcategory.
     100% backwards compatible with the original behaviour.

  2. **Selection mode** (one or more selection flags present):
     Applies --to category to a filtered subset of transactions.
     --from is optional; when present it further narrows the selection.
"""

import re
from datetime import date  # noqa: E402 — needed before typer import

import typer

from gilt.model.account import Transaction, TransactionGroup
from gilt.services.transaction_operations_service import (
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.services.transaction_query_service import TransactionFilter, TransactionQueryService
from gilt.workspace import Workspace

from .util import (
    apply_categorization_updates,
    console,
    display_transaction_matches,
    find_matches_by_criteria,
    fmt_amount_str,
    load_account_transactions,
    parse_category_path,
    print_dry_run_message,
    print_error,
    require_event_sourcing,
    require_persistence_service,
)

# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------


def _validate_selection_flags(
    desc_prefix: str | None,
    pattern: str | None,
    amount_eq: float | None,
    amount_min: float | None,
    amount_max: float | None,
) -> str | None:
    """Validate mutually exclusive selection flags.

    Returns an error message string if invalid, or None if valid.
    """
    if desc_prefix is not None and pattern is not None:
        return "--desc-prefix and --pattern cannot both be set; choose one"

    if amount_eq is not None and (amount_min is not None or amount_max is not None):
        return "--amount-eq cannot be combined with --amount-min or --amount-max"

    if pattern is not None:
        try:
            re.compile(pattern, re.IGNORECASE)
        except re.error as exc:
            return f"Invalid regex pattern: {exc}"

    return None


# ---------------------------------------------------------------------------
# Transaction filtering (works on Transaction objects via TransactionQueryService)
# ---------------------------------------------------------------------------


def _build_transaction_filter(
    account: str | None,
    date_from: date | None,
    date_to: date | None,
    fy_range: tuple[date, date] | None,
    amount_eq: float | None,
    amount_min: float | None,
    amount_max: float | None,
    from_cat: str | None,
    from_subcat: str | None,
) -> TransactionFilter:
    """Build a TransactionFilter from the supplied selection criteria.

    fy_range takes precedence over date_from/date_to when both are supplied.
    """
    if fy_range is not None:
        effective_fy_range = fy_range
    elif date_from is not None or date_to is not None:
        effective_fy_range = (
            date_from or date.min,
            date_to or date.max,
        )
    else:
        effective_fy_range = None

    return TransactionFilter(
        account_id=account,
        fy_range=effective_fy_range,
        amount_eq=amount_eq,
        amount_min=amount_min,
        amount_max=amount_max,
        category=from_cat,
        subcategory=from_subcat,
    )


# ---------------------------------------------------------------------------
# Match finders
# ---------------------------------------------------------------------------


def _find_matching_transactions(
    all_transactions: list[dict],
    from_cat: str,
    from_subcat: str | None,
) -> list[tuple[str, TransactionGroup]]:
    """Find transactions matching the given category/subcategory (rename mode)."""
    matches: list[tuple[str, TransactionGroup]] = []
    for row in all_transactions:
        if row.get("category") != from_cat:
            continue
        if from_subcat is not None and row.get("subcategory") != from_subcat:
            continue
        group = TransactionGroup.from_projection_row(row)
        matches.append((row["account_id"], group))
    return matches


# ---------------------------------------------------------------------------
# Display
# ---------------------------------------------------------------------------


def _display_matches(
    matches: list[tuple[str, TransactionGroup]],
    from_label: str | None,
    to_category: str,
) -> None:
    """Display matched transactions in a table.

    When ``from_label`` is None (selection mode without explicit --from),
    the "From" column shows the transaction's current category.
    """

    def row_fn(item: tuple[str, TransactionGroup]) -> tuple:
        account_id, group = item
        t = group.primary
        if from_label is not None:
            from_col = from_label
        else:
            current = t.category or "—"
            if t.subcategory:
                current += f":{t.subcategory}"
            from_col = current
        return (
            account_id,
            t.transaction_id[:8],
            str(t.date),
            (t.description or "")[:40],
            fmt_amount_str(t.amount),
            from_col,
            to_category,
        )

    display_transaction_matches(
        "Transactions to Recategorize",
        [("From", {"style": "red"}), ("→ To", {"style": "green"})],
        matches,
        row_fn,
    )


# ---------------------------------------------------------------------------
# Apply helpers
# ---------------------------------------------------------------------------


def _confirm_and_apply_renaming(
    all_matches: list[tuple[str, TransactionGroup]],
    to_cat: str,
    to_subcat: str | None,
    workspace: Workspace,
    total_matched: int,
) -> int:
    """Confirm with user and apply category renaming. Returns exit code."""
    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1

    import sys

    if sys.stdin.isatty() and not typer.confirm(
        f"Rename category in {total_matched} transaction(s)?"
    ):
        console.print("Cancelled")
        return 0

    _apply_renaming(all_matches, to_cat, to_subcat, ready, workspace)
    console.print(f"[green]✓[/] Renamed category in {total_matched} transaction(s)")
    return 0


def _apply_renaming(
    matches: list[tuple[str, TransactionGroup]],
    to_cat: str,
    to_subcat: str | None,
    ready,
    workspace: Workspace,
) -> None:
    """Apply category renaming to matched transactions."""
    persistence_svc = require_persistence_service(ready, workspace)
    persistence_svc.persist_category_rename(
        matches=matches,
        to_category=to_cat,
        to_subcategory=to_subcat,
    )


def _apply_categorization(
    all_matches: list[tuple[str, TransactionGroup]],
    to_cat: str,
    to_subcat: str | None,
    workspace: Workspace,
    total_matched: int,
) -> int:
    """Confirm with user and apply categorization in selection mode. Returns exit code."""
    ready = require_event_sourcing(workspace)
    if ready is None:
        return 1

    import sys

    if sys.stdin.isatty() and not typer.confirm(
        f"Recategorize {total_matched} transaction(s) to '{to_cat}"
        + (f":{to_subcat}" if to_subcat else "")
        + "'?"
    ):
        console.print("Cancelled")
        return 0

    from gilt.services.categorization_persistence_service import CategorizationUpdate

    updates = [
        CategorizationUpdate(
            transaction_id=group.primary.transaction_id,
            account_id=account_id,
            category=to_cat,
            subcategory=to_subcat,
            source="user",
            confidence=1.0,
        )
        for account_id, group in all_matches
    ]
    apply_categorization_updates(ready, workspace, updates)
    console.print(f"[green]✓[/] Recategorized {total_matched} transaction(s)")
    return 0


# ---------------------------------------------------------------------------
# Mode implementations
# ---------------------------------------------------------------------------


def _run_rename_mode(
    *,
    from_category: str,
    to_category: str,
    to_cat: str,
    to_subcat: str | None,
    workspace: Workspace,
    write: bool,
) -> int:
    """Handle rename mode: find by category and rename to to_category."""
    from_cat, from_subcat, _ = parse_category_path(from_category)
    if not from_cat:
        print_error("--from category cannot be empty")
        return 1

    all_transactions = load_account_transactions(workspace, None)
    if all_transactions is None:
        return 1

    all_matches = _find_matching_transactions(all_transactions, from_cat, from_subcat)
    total_matched = len(all_matches)

    if total_matched == 0:
        console.print(f"[yellow]No transactions found with category '{from_category}'[/]")
        return 0

    _display_matches(all_matches, from_category, to_category)
    console.print(f"\n[bold]Total:[/] {total_matched} transaction(s)")

    if not write:
        print_dry_run_message()
        return 0

    return _confirm_and_apply_renaming(all_matches, to_cat, to_subcat, workspace, total_matched)


def _build_text_matches(
    filtered_transactions: list[Transaction],
    desc_prefix: str | None,
    pattern: str | None,
    service: TransactionOperationsService | None,
) -> list[tuple[str, TransactionGroup]] | None:
    """Apply text matching via service layer. Returns None on error."""
    if service is None:
        service = TransactionOperationsService()
    criteria = SearchCriteria(desc_prefix=desc_prefix, pattern=pattern)
    groups_by_account: dict[str, list[TransactionGroup]] = {}
    for t in filtered_transactions:
        groups_by_account.setdefault(t.account_id, []).append(
            TransactionGroup(group_id=t.transaction_id, primary=t)
        )
    return find_matches_by_criteria(groups_by_account, criteria, service)


def _run_selection_mode(
    *,
    from_category: str | None,
    to_category: str,
    to_cat: str,
    to_subcat: str | None,
    account: str | None,
    desc_prefix: str | None,
    pattern: str | None,
    amount_eq: float | None,
    amount_min: float | None,
    amount_max: float | None,
    date_from: date | None,
    date_to: date | None,
    fy_range: tuple[date, date] | None,
    workspace: Workspace,
    write: bool,
    service: TransactionOperationsService | None,
) -> int:
    """Handle selection mode: filter rows then apply to_category."""
    flag_error = _validate_selection_flags(desc_prefix, pattern, amount_eq, amount_min, amount_max)
    if flag_error is not None:
        print_error(flag_error)
        return 1

    from_cat: str | None = None
    from_subcat: str | None = None
    if from_category:
        from_cat, from_subcat, _ = parse_category_path(from_category)
        if not from_cat:
            print_error("--from category cannot be empty")
            return 1

    all_rows = load_account_transactions(workspace, None)
    if all_rows is None:
        return 1

    criteria = _build_transaction_filter(
        account=account,
        date_from=date_from,
        date_to=date_to,
        fy_range=fy_range,
        amount_eq=amount_eq,
        amount_min=amount_min,
        amount_max=amount_max,
        from_cat=from_cat,
        from_subcat=from_subcat,
    )
    all_candidates = [Transaction.from_projection_row(row) for row in all_rows]
    filtered_transactions = TransactionQueryService().find_matching(all_candidates, criteria)

    if not filtered_transactions:
        console.print("[yellow]No transactions match the given filters[/]")
        return 0

    if desc_prefix is not None or pattern is not None:
        all_matches = _build_text_matches(filtered_transactions, desc_prefix, pattern, service)
        if all_matches is None:
            return 1
    else:
        all_matches = [
            (t.account_id, TransactionGroup(group_id=t.transaction_id, primary=t))
            for t in filtered_transactions
        ]

    if not all_matches:
        console.print("[yellow]No transactions match the given filters[/]")
        return 0

    _display_matches(all_matches, from_category or None, to_category)
    console.print(f"\n[bold]Total:[/] {len(all_matches)} transaction(s)")

    if not write:
        print_dry_run_message()
        return 0

    return _apply_categorization(all_matches, to_cat, to_subcat, workspace, len(all_matches))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run(
    *,
    to_category: str,
    workspace: Workspace,
    from_category: str | None = None,
    account: str | None = None,
    desc_prefix: str | None = None,
    pattern: str | None = None,
    amount_eq: float | None = None,
    amount_min: float | None = None,
    amount_max: float | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    fy_range: tuple[date, date] | None = None,
    write: bool = False,
    service: TransactionOperationsService | None = None,
) -> int:
    """Rename a category or recategorize a filtered selection.

    Modes:

    **Rename mode** (no selection flags):
      Renames every transaction with ``from_category`` to ``to_category``.
      ``from_category`` is required in this mode.

    **Selection mode** (one or more selection flags are present):
      Applies ``to_category`` to the subset of transactions matching the
      supplied filters.  ``from_category`` is optional; when supplied it
      further restricts the selection to that existing category.

    Selection flags: ``account``, ``desc_prefix``, ``pattern``,
    ``amount_eq``, ``amount_min``, ``amount_max``, ``date_from``,
    ``date_to``, ``fy_range``.

    Args:
        to_category: New category name (supports ``"Category:Subcategory"`` syntax)
        workspace: Workspace for resolving data paths
        from_category: Original category name — required in rename mode,
            optional narrowing filter in selection mode
        account: Restrict to this account ID
        desc_prefix: Description prefix filter (case-insensitive)
        pattern: Regex pattern filter on descriptions
        amount_eq: Exact (signed) amount to match
        amount_min: Minimum amount (signed, inclusive)
        amount_max: Maximum amount (signed, inclusive)
        date_from: Start date (inclusive)
        date_to: End date (inclusive)
        fy_range: Fiscal-year date range as ``(start, end)``
        write: Persist changes (default: dry-run)
        service: Injected TransactionOperationsService (for testing)

    Returns:
        Exit code (0 success, 1 error)
    """
    to_cat, to_subcat, _ = parse_category_path(to_category)
    if not to_cat:
        print_error("--to category cannot be empty")
        return 1

    selection_mode = any(
        x is not None
        for x in (
            desc_prefix,
            pattern,
            amount_eq,
            amount_min,
            amount_max,
            account,
            date_from,
            date_to,
            fy_range,
        )
    )

    if not selection_mode:
        if not from_category:
            print_error(
                "Specify --from to rename a category, or add selection flags "
                "(--desc-prefix, --pattern, --amount-eq, --account, --date-from/--date-to, --fy) "
                "to recategorize a filtered set"
            )
            return 1
        return _run_rename_mode(
            from_category=from_category,
            to_category=to_category,
            to_cat=to_cat,
            to_subcat=to_subcat,
            workspace=workspace,
            write=write,
        )

    return _run_selection_mode(
        from_category=from_category,
        to_category=to_category,
        to_cat=to_cat,
        to_subcat=to_subcat,
        account=account,
        desc_prefix=desc_prefix,
        pattern=pattern,
        amount_eq=amount_eq,
        amount_min=amount_min,
        amount_max=amount_max,
        date_from=date_from,
        date_to=date_to,
        fy_range=fy_range,
        workspace=workspace,
        write=write,
        service=service,
    )


__all__ = ["run"]
