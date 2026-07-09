from __future__ import annotations

"""CLI command: show categorization history for a description pattern."""

from datetime import date

from gilt.workspace import Workspace

from ..event_sourcing_bootstrap import require_projections
from .history_view import display_history_table, print_invalid_date, print_no_matches


def run(
    *,
    pattern: str,
    account: str | None = None,
    include_uncategorized: bool = False,
    limit: int = 10,
    date_from: str | None = None,
    date_to: str | None = None,
    workspace: Workspace,
) -> int:
    """Show categorization history for transactions matching a description pattern.

    Groups matching transactions by category/subcategory and displays counts,
    sums, min/max amounts, and the most recent date seen.

    Returns:
        0 on success (including empty results), 1 on missing projections, 2 on bad dates.
    """
    if date_from is not None:
        try:
            date.fromisoformat(date_from)
        except ValueError:
            print_invalid_date("date-from", date_from)
            return 2

    if date_to is not None:
        try:
            date.fromisoformat(date_to)
        except ValueError:
            print_invalid_date("date-to", date_to)
            return 2

    builder = require_projections(workspace)
    rows = builder.find_category_history(
        pattern,
        account_id=account,
        include_uncategorized=include_uncategorized,
        limit=limit,
        date_from=date_from,
        date_to=date_to,
    )

    if not rows:
        print_no_matches(pattern)
        return 0

    display_history_table(rows, pattern, account, date_from, date_to)
    return 0
