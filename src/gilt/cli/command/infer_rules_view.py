"""Rich rendering functions for the infer-rules command."""

from __future__ import annotations

from rich.table import Table

from gilt.model.category_io import format_category_path

from ..console import console, display_transaction_matches
from ..formatting import fmt_amount_str


def display_rules(rules) -> None:
    table = Table(title="Inferred Categorization Rules", show_lines=False)
    table.add_column("Description", style="white")
    table.add_column("Category", style="green")
    table.add_column("Evidence", style="cyan", justify="right")
    table.add_column("Confidence", style="blue", justify="right")

    for rule in rules:
        cat_display = format_category_path(rule.category, rule.subcategory)
        table.add_row(
            rule.description[:60],
            cat_display,
            f"{rule.evidence_count}/{rule.total_count}",
            f"{rule.confidence:.0%}",
        )

    console.print("\n")
    console.print(table)
    console.print(f"\n[dim]{len(rules)} rule(s) inferred[/dim]")


def display_matches(matches) -> None:
    def row_fn(m) -> tuple:
        txn = m.transaction
        cat_display = format_category_path(m.rule.category, m.rule.subcategory)
        return (
            txn.get("account_id", ""),
            txn["transaction_id"][:8],
            txn.get("transaction_date", ""),
            (txn.get("canonical_description") or "")[:50],
            fmt_amount_str(txn.get("amount", 0)),
            cat_display,
            f"{m.rule.evidence_count}/{m.rule.total_count}",
        )

    console.print("\n")
    display_transaction_matches(
        "Transactions Matching Rules",
        [
            ("Inferred Category", {"style": "green"}),
            ("Evidence", {"style": "blue", "justify": "right"}),
        ],
        matches,
        row_fn,
    )
