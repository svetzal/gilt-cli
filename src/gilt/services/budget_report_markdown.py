from __future__ import annotations

"""
Budget report Markdown rendering — pure serialization, no I/O.

Entry point: dump_budget_report_markdown(report) -> str

All functions are module-level and accept only data from budget_report_model;
no UI library dependencies (rich, typer, PySide6).
"""

from datetime import date

from gilt.services.budget_report_model import BudgetReport, BudgetSummaryLine


def _fmt(amount: float) -> str:
    return f"${amount:,.2f}"


def _esc_md(s: str) -> str:
    return s.replace("|", "\\|")


def _render_header(
    year: int | None,
    month: int | None,
    generated_date: date,
) -> list[str]:
    if year and month:
        title = f"Budget Report - {year}-{month:02d}"
        period_desc = f"{year}-{month:02d}"
    elif year:
        title = f"Budget Report - {year}"
        period_desc = str(year)
    else:
        title = "Budget Report"
        period_desc = "All Time"

    return [
        f"# {title}\n",
        f"**Period:** {period_desc}\n",
        f"**Generated:** {generated_date.isoformat()}\n",
        "",
    ]


def _render_summary_table(report: BudgetReport) -> list[str]:
    lines = [
        "## Budget Summary\n",
        "| Category | Budget | Actual | Remaining | % Used |",
        "|----------|--------|--------|-----------|--------|",
    ]
    for line in report.lines:
        budget_str = _fmt(line.budget_amount) if line.budget_amount is not None else "—"
        actual_str = _fmt(line.actual_amount)
        remaining_str = _fmt(line.remaining) if line.remaining is not None else "—"
        pct_str = f"{line.percent_used:.1f}%" if line.percent_used is not None else "—"
        lines.append(
            f"| {line.category_name} | {budget_str} | {actual_str} | {remaining_str} | {pct_str} |"
        )

    total_pct = report.percent_used
    lines.append(
        f"| **TOTAL** | **{_fmt(report.total_budgeted)}** | **{_fmt(report.total_actual)}** | **{_fmt(report.total_remaining)}** | **{total_pct:.1f}%** |"
    )
    lines.append("")
    return lines


def _render_category_detail(
    line: BudgetSummaryLine,
    report: BudgetReport,
) -> list[str]:
    if line.actual_amount == 0 and line.budget_amount is None:
        return []

    output: list[str] = [f"### {line.category_name}\n"]

    if line.description:
        output.append(f"*{line.description}*\n")

    if line.budget_amount is not None:
        remaining = line.remaining or 0.0
        pct = line.percent_used or 0.0
        if remaining < 0:
            status = "⚠️ OVER BUDGET"
        elif pct < 90:
            status = "✓ On Track"
        else:
            status = "⚠️ Near Limit"
        output.append(f"- **Budget:** {_fmt(line.budget_amount)}")
        output.append(f"- **Actual:** {_fmt(line.actual_amount)}")
        output.append(f"- **Remaining:** {_fmt(remaining)}")
        output.append(f"- **% Used:** {pct:.1f}%")
        output.append(f"- **Status:** {status}")
    else:
        output.append(f"- **Actual:** {_fmt(line.actual_amount)}")

    if report.month is not None:
        txns = report.transactions_by_category.get(line.category_name, [])
        if txns:
            output.append("")
            output.append("| Date | Description | Subcategory | Amount | Account |")
            output.append("|------|-------------|-------------|--------|---------|")
            for detail in txns:
                output.append(
                    f"| {detail.date_str} | {_esc_md(detail.description)} | {_esc_md(detail.subcategory)} | {_fmt(detail.amount)} | {_esc_md(detail.account_id)} |"
                )
    elif line.subcategory_order and line.subcategory_actuals:
        output.append("\n**Subcategories:**\n")
        for subcat_name in line.subcategory_order:
            subcat_actual = line.subcategory_actuals.get(subcat_name, 0.0)
            if subcat_actual > 0:
                pct_of_cat = (
                    (subcat_actual / line.actual_amount * 100) if line.actual_amount > 0 else 0
                )
                output.append(
                    f"- {subcat_name}: {_fmt(subcat_actual)} ({pct_of_cat:.1f}% of category)"
                )

    output.append("")
    return output


def _render_footer(report: BudgetReport) -> list[str]:
    lines = [
        "---\n",
        "## Summary\n",
        f"- **Total Budgeted:** {_fmt(report.total_budgeted)}",
        f"- **Total Actual:** {_fmt(report.total_actual)}",
        f"- **Total Remaining:** {_fmt(report.total_remaining)}",
        f"- **Overall % Used:** {report.percent_used:.1f}%",
    ]
    if report.over_budget_count > 0:
        n = report.over_budget_count
        cat_word = "category" if n == 1 else "categories"
        lines.append(f"\n⚠️ **{n} {cat_word} over budget**")
    return lines


def dump_budget_report_markdown(report: BudgetReport) -> str:
    """Serialize a BudgetReport to a Markdown string.

    Pure function — no I/O, no UI library dependencies.
    """
    lines: list[str] = []
    lines.extend(_render_header(report.year, report.month, report.generated_date))
    lines.extend(_render_summary_table(report))
    lines.append("## Detailed Breakdown\n")
    for line in report.lines:
        lines.extend(_render_category_detail(line, report))
    lines.extend(_render_footer(report))
    return "\n".join(lines)


__all__ = ["dump_budget_report_markdown"]
