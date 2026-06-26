"""Rich rendering functions for the diagnose-duplicates command."""

from __future__ import annotations

from rich.table import Table

from gilt.services.duplicate_diagnostics_service import DuplicateIssue

from ..console import console


def display_issues(issues: list[DuplicateIssue]) -> None:
    """Display the duplicate issues table and a summary line."""
    sorted_issues = sorted(issues, key=lambda i: (i.issue_class, i.transaction_date))

    table = Table(title="Duplicate Projection Issues", show_lines=False)
    table.add_column("TxID", style="cyan", no_wrap=True)
    table.add_column("Date", style="white")
    table.add_column("Account", style="blue")
    table.add_column("Description", style="white")
    table.add_column("Amount", style="yellow", justify="right")
    table.add_column("Issue", style="red")
    table.add_column("Points At", style="dim")

    for issue in sorted_issues:
        table.add_row(
            issue.transaction_id[:8],
            issue.transaction_date,
            issue.account_id,
            issue.canonical_description[:40],
            f"{issue.amount:,.2f}",
            issue.issue_class,
            issue.primary_pointed_at[:8] if issue.primary_pointed_at else "—",
        )

    console.print(table)

    orphan_count = sum(1 for i in issues if i.issue_class == "orphan_group")
    stale_count = sum(1 for i in issues if i.issue_class == "stale_primary")
    self_ref_count = sum(1 for i in issues if i.issue_class == "self_referential")

    parts = []
    if orphan_count:
        parts.append(f"{orphan_count} orphan")
    if stale_count:
        parts.append(f"{stale_count} stale")
    if self_ref_count:
        parts.append(f"{self_ref_count} self-ref")

    console.print(
        f"\n[yellow]Found {len(issues)} issue(s):[/] {', '.join(parts)}\n"
        "[dim]Run 'gilt rebuild-projections --from-scratch' to attempt auto-repair.[/dim]"
    )
