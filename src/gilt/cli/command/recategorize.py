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
from dataclasses import dataclass
from datetime import date

from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category_io import format_category_path
from gilt.services.transaction_operations_service import (
    SearchCriteria,
    TransactionOperationsService,
)
from gilt.services.transaction_query_service import TransactionFilter, TransactionQueryService
from gilt.util.dates import parse_iso_date
from gilt.workspace import Workspace

from ..console import print_error, print_match_total
from ..event_sourcing_bootstrap import require_persistence_service
from ..filtering import match_from_row, match_from_transaction
from ..formatting import build_category_path
from ..loaders import load_account_transactions
from ..mutations import (
    find_matches_by_criteria,
    persist_categorization_matches,
    run_persisted_mutation,
)
from . import recategorize_view
from ._errors import CommandAbort


@dataclass(frozen=True)
class RecategorizeSelection:
    from_category: str | None
    to_category: str
    to_cat: str
    to_subcat: str | None
    account: str | None
    desc_prefix: str | None
    pattern: str | None
    amount_eq: float | None
    amount_min: float | None
    amount_max: float | None
    date_from: date | None
    date_to: date | None
    fy_range: tuple[date, date] | None
    write: bool
    service: TransactionOperationsService | None


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
        matches.append(match_from_row(row))
    return matches


# ---------------------------------------------------------------------------
# Apply helpers
# ---------------------------------------------------------------------------


def _run_renaming(
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
    from_cat, from_subcat, _ = build_category_path(from_category)
    if not from_cat:
        print_error("--from category cannot be empty")
        raise CommandAbort(1)

    all_transactions = load_account_transactions(workspace, None)
    all_matches = _find_matching_transactions(all_transactions, from_cat, from_subcat)
    total_matched = len(all_matches)

    if total_matched == 0:
        recategorize_view.print_no_transactions_for_category(from_category)
        return 0

    def display() -> None:
        recategorize_view.display_recategorize_matches(all_matches, from_category, to_category)
        print_match_total(total_matched)

    return run_persisted_mutation(
        matches=all_matches,
        display=display,
        confirm_prompt=f"Rename category in {total_matched} transaction(s)?",
        assume_yes=False,
        write=write,
        workspace=workspace,
        persist=lambda ready: _run_renaming(all_matches, to_cat, to_subcat, ready, workspace),
        on_success=lambda: recategorize_view.print_renamed_success(total_matched),
    )


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
        acct_id, group = match_from_transaction(t)
        groups_by_account.setdefault(acct_id, []).append(group)
    return find_matches_by_criteria(groups_by_account, criteria, service)


def _run_selection_mode(selection: RecategorizeSelection, workspace: Workspace) -> int:
    """Handle selection mode: filter rows then apply to_category."""
    flag_error = _validate_selection_flags(
        selection.desc_prefix,
        selection.pattern,
        selection.amount_eq,
        selection.amount_min,
        selection.amount_max,
    )
    if flag_error is not None:
        print_error(flag_error)
        raise CommandAbort(1)

    from_cat: str | None = None
    from_subcat: str | None = None
    if selection.from_category:
        from_cat, from_subcat, _ = build_category_path(selection.from_category)
        if not from_cat:
            print_error("--from category cannot be empty")
            raise CommandAbort(1)

    all_rows = load_account_transactions(workspace, None)

    criteria = _build_transaction_filter(
        account=selection.account,
        date_from=selection.date_from,
        date_to=selection.date_to,
        fy_range=selection.fy_range,
        amount_eq=selection.amount_eq,
        amount_min=selection.amount_min,
        amount_max=selection.amount_max,
        from_cat=from_cat,
        from_subcat=from_subcat,
    )
    all_candidates = [Transaction.from_projection_row(row) for row in all_rows]
    filtered_transactions = TransactionQueryService().find_matching(all_candidates, criteria)

    if not filtered_transactions:
        recategorize_view.print_no_filter_matches()
        return 0

    if selection.desc_prefix is not None or selection.pattern is not None:
        all_matches = _build_text_matches(
            filtered_transactions, selection.desc_prefix, selection.pattern, selection.service
        )
        if all_matches is None:
            raise CommandAbort(1)
    else:
        all_matches = [match_from_transaction(t) for t in filtered_transactions]

    if not all_matches:
        recategorize_view.print_no_filter_matches()
        return 0

    total_matched = len(all_matches)

    def display() -> None:
        recategorize_view.display_recategorize_matches(
            all_matches, selection.from_category or None, selection.to_category
        )
        print_match_total(total_matched)

    return run_persisted_mutation(
        matches=all_matches,
        display=display,
        confirm_prompt=f"Recategorize {total_matched} transaction(s) to '{format_category_path(selection.to_cat, selection.to_subcat)}'?",
        assume_yes=False,
        write=selection.write,
        workspace=workspace,
        persist=lambda ready: persist_categorization_matches(
            all_matches, selection.to_cat, selection.to_subcat, ready, workspace, source="user"
        ),
        on_success=lambda: recategorize_view.print_recategorized_success(total_matched),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def _build_to_category(to_category: str) -> tuple[str, str | None]:
    """Parse and validate to_category. Returns (to_cat, to_subcat) or raises CommandAbort(1) on empty."""
    to_cat, to_subcat, _ = build_category_path(to_category)
    if not to_cat:
        print_error("--to category cannot be empty")
        raise CommandAbort(1)
    return to_cat, to_subcat


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
    to_cat, to_subcat = _build_to_category(to_category)
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
            raise CommandAbort(1)
        return _run_rename_mode(
            from_category=from_category,
            to_category=to_category,
            to_cat=to_cat,
            to_subcat=to_subcat,
            workspace=workspace,
            write=write,
        )

    selection = RecategorizeSelection(
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
        write=write,
        service=service,
    )
    return _run_selection_mode(selection, workspace)


def build_date_selection(
    date_from_str: str | None,
    date_to_str: str | None,
    fy: str | None,
) -> tuple[date | None, date | None, tuple[date, date] | None] | str:
    """Parse and validate date/fiscal-year CLI inputs.

    Returns a ``(date_from, date_to, fy_range)`` triple on success, or a plain
    ``str`` error message when the inputs are invalid.

    Rules:
    - ``--fy`` and ``--date-from``/``--date-to`` are mutually exclusive.
    - Date strings must be in ISO-8601 format (``YYYY-MM-DD``).
    - The fiscal year string must match the ``FY25`` / ``FY2025`` pattern.
    """
    from gilt.util.fy import fiscal_year_range

    if fy is not None and (date_from_str is not None or date_to_str is not None):
        return "--fy and --date-from/--date-to cannot be used together"

    date_from: date | None = None
    if date_from_str is not None:
        try:
            date_from = parse_iso_date(date_from_str)
        except ValueError:
            return f"Invalid --date-from value: {date_from_str!r}. Expected YYYY-MM-DD"

    date_to: date | None = None
    if date_to_str is not None:
        try:
            date_to = parse_iso_date(date_to_str)
        except ValueError:
            return f"Invalid --date-to value: {date_to_str!r}. Expected YYYY-MM-DD"

    fy_range: tuple[date, date] | None = None
    if fy is not None:
        try:
            fy_range = fiscal_year_range(fy)
        except ValueError as exc:
            return str(exc)

    return date_from, date_to, fy_range


__all__ = ["build_date_selection", "run"]
