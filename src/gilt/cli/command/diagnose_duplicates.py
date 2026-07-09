from __future__ import annotations

"""
Diagnose duplicate-projection issues: orphan groups, stale primaries, self-referential rows.
"""

from gilt.services.duplicate_diagnostics_service import DuplicateDiagnosticsService
from gilt.workspace import Workspace

from ..event_sourcing_bootstrap import require_projections
from .diagnose_duplicates_view import display_issues, print_no_issues


def run(
    *,
    workspace: Workspace,
) -> int:
    """Diagnose duplicate-projection issues in the projections database.

    Scans all rows (including duplicates) and reports:
    - orphan_group: connected component where no member has is_duplicate=0
    - stale_primary: primary_transaction_id points at a non-existent or itself-duplicate row
    - self_referential: primary_transaction_id == transaction_id

    Args:
        workspace: Workspace providing paths to the projections database

    Returns:
        Exit code (0 if no issues, 1 if issues found)
    """
    projection_builder = require_projections(workspace)
    if projection_builder is None:
        return 1

    rows = projection_builder.get_all_transactions(include_duplicates=True)

    service = DuplicateDiagnosticsService()
    issues = service.find_issues(rows)

    if not issues:
        print_no_issues()
        return 0

    display_issues(issues)
    return 1


__all__ = ["run"]
