from __future__ import annotations

"""
Receipt attachment coverage report.

Shows which transactions in a given category have receipts attached vs not,
grouped by (category, subcategory) or by account_id.
"""

from datetime import date

from rich.console import Console

from gilt.services.receipts_service import build_receipt_coverage
from gilt.workspace import Workspace

from ..console import console as _default_console
from ..event_sourcing_bootstrap import require_projections
from .receipts_view import render_missing, render_summary


def run(
    *,
    category: str = "Mojility",
    by_account: bool = False,
    fy_range: tuple[date, date] | None = None,
    fy_label: str | None = None,
    missing: bool = False,
    workspace: Workspace,
    _console: Console | None = None,
) -> int:
    """Display receipt attachment coverage for categorised transactions.

    Read-only. Queries the projections database and shows coverage statistics.

    Args:
        category: Category to filter on (default "Mojility").
        by_account: Group by account_id instead of (category, subcategory).
        fy_range: Optional (start, end) date range to restrict results.
        fy_label: Human-readable fiscal year label for the title (e.g. "FY25").
        missing: If True, list individual transactions without receipts instead
            of the summary table.
        workspace: Workspace providing data paths.
        _console: Optional Rich Console for testing.

    Returns:
        Exit code (0 success, 1 error).
    """
    con = _console if _console is not None else _default_console

    projection_builder = require_projections(workspace)
    rows = projection_builder.get_all_transactions(include_duplicates=False)

    result = build_receipt_coverage(
        rows,
        category=category,
        group_by_account=by_account,
        fy_range=fy_range,
    )

    if not result.coverage_rows:
        con.print(f"[dim]No {category!r} transactions found.[/dim]")
        return 0

    if missing:
        render_missing(result, con)
    else:
        render_summary(result, category=category, by_account=by_account, fy_label=fy_label, con=con)

    return 0


__all__ = ["run"]
