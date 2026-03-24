from __future__ import annotations

"""
Budget Reporting Service - pure business logic for budget report generation.

Accepts Transaction objects directly; no file I/O, no projections database,
no UI imports (rich, typer, PySide6).
"""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from gilt.model.account import Transaction
from gilt.model.category import Budget, BudgetPeriod, CategoryConfig


@dataclass
class ExpenseDetail:
    """A single expense transaction for display in a report."""

    date_str: str
    description: str
    subcategory: str
    amount: float
    account_id: str


@dataclass
class BudgetSummaryLine:
    """One row in the budget summary table — one category."""

    category_name: str
    description: str | None
    budget_amount: float | None
    actual_amount: float
    remaining: float | None
    percent_used: float | None
    is_over_budget: bool
    subcategory_actuals: dict[str, float] = field(default_factory=dict)


@dataclass
class BudgetReport:
    """Complete computed budget report, ready for rendering."""

    year: int | None
    month: int | None
    generated_date: date
    lines: list[BudgetSummaryLine]
    transactions_by_category: dict[str, list[ExpenseDetail]]
    total_budgeted: float
    total_actual: float
    total_remaining: float
    percent_used: float
    over_budget_count: int


class BudgetReportingService:
    """Pure business logic for budget reporting.

    Accepts a CategoryConfig at construction time. All methods accept
    Transaction objects directly and return plain data structures.
    Never imports rich, typer, or PySide6.
    """

    def __init__(self, category_config: CategoryConfig) -> None:
        self._category_config = category_config

    # ------------------------------------------------------------------
    # Core aggregation
    # ------------------------------------------------------------------

    def aggregate_spending(
        self,
        transactions: list[Transaction],
        *,
        year: int | None,
        month: int | None,
    ) -> dict[tuple[str, str | None], float]:
        """Sum expense amounts by (category, subcategory) for the period.

        Only negative-amount transactions (expenses) are counted.
        Transactions without a category are skipped.

        Returns a dict mapping (category, subcategory) to total absolute amount.
        """
        spending: dict[tuple[str, str | None], float] = defaultdict(float)
        for txn in transactions:
            if not txn.category:
                continue
            if year is not None and txn.date.year != year:
                continue
            if month is not None and txn.date.month != month:
                continue
            key = (txn.category, txn.subcategory)
            spending[key] += abs(txn.amount) if txn.amount < 0 else 0.0
        return dict(spending)

    def collect_expense_transactions(
        self,
        transactions: list[Transaction],
        *,
        year: int | None,
        month: int | None,
    ) -> dict[str, list[ExpenseDetail]]:
        """Group expense transactions by category for detailed display.

        Only negative-amount (expense) transactions are included.
        Each category maps to a list of ExpenseDetail, sorted deterministically
        by (date asc, amount asc, description asc).
        """
        result: dict[str, list[ExpenseDetail]] = defaultdict(list)
        for txn in transactions:
            if not txn.category:
                continue
            if year is not None and txn.date.year != year:
                continue
            if month is not None and txn.date.month != month:
                continue
            if txn.amount >= 0:
                continue
            result[txn.category].append(
                ExpenseDetail(
                    date_str=str(txn.date),
                    description=txn.description or "",
                    subcategory=txn.subcategory or "",
                    amount=abs(txn.amount),
                    account_id=txn.account_id or "",
                )
            )

        for items in result.values():
            items.sort(key=lambda x: (x.date_str, x.amount, x.description))

        return dict(result)

    # ------------------------------------------------------------------
    # Budget period calculation
    # ------------------------------------------------------------------

    def budget_for_period(self, budget: Budget | None, month: int | None) -> float | None:
        """Return the budget amount adjusted for the report period.

        For a monthly report (month is not None):
          - monthly budget → use as-is
          - yearly budget → divide by 12

        For a yearly report (month is None):
          - yearly budget → use as-is
          - monthly budget → multiply by 12

        Returns None when no budget is defined.
        """
        if not budget:
            return None
        if month is not None:
            if budget.period == BudgetPeriod.monthly:
                return budget.amount
            return budget.amount / 12
        if budget.period == BudgetPeriod.yearly:
            return budget.amount
        return budget.amount * 12

    # ------------------------------------------------------------------
    # Report assembly
    # ------------------------------------------------------------------

    def generate_report(
        self,
        transactions: list[Transaction],
        *,
        year: int | None,
        month: int | None,
    ) -> BudgetReport:
        """Assemble a complete BudgetReport from a list of transactions."""
        spending = self.aggregate_spending(transactions, year=year, month=month)
        transactions_by_category = self.collect_expense_transactions(
            transactions, year=year, month=month
        )

        lines: list[BudgetSummaryLine] = []
        total_budgeted = 0.0
        total_actual = 0.0
        over_budget_count = 0

        for cat in self._category_config.categories:
            budget_amount = self.budget_for_period(cat.budget, month)
            cat_actual, subcat_actuals = self._actual_for_category(cat.name, spending)

            remaining: float | None = None
            percent_used: float | None = None
            is_over_budget = False

            if budget_amount is not None:
                remaining = budget_amount - cat_actual
                percent_used = (cat_actual / budget_amount * 100) if budget_amount > 0 else 0.0
                total_budgeted += budget_amount
                if cat_actual > budget_amount:
                    is_over_budget = True
                    over_budget_count += 1

            total_actual += cat_actual

            lines.append(
                BudgetSummaryLine(
                    category_name=cat.name,
                    description=cat.description,
                    budget_amount=budget_amount,
                    actual_amount=cat_actual,
                    remaining=remaining,
                    percent_used=percent_used,
                    is_over_budget=is_over_budget,
                    subcategory_actuals=subcat_actuals,
                )
            )

        total_remaining = total_budgeted - total_actual
        overall_pct = (total_actual / total_budgeted * 100) if total_budgeted > 0 else 0.0

        return BudgetReport(
            year=year,
            month=month,
            generated_date=date.today(),
            lines=lines,
            transactions_by_category=transactions_by_category,
            total_budgeted=total_budgeted,
            total_actual=total_actual,
            total_remaining=total_remaining,
            percent_used=overall_pct,
            over_budget_count=over_budget_count,
        )

    # ------------------------------------------------------------------
    # Markdown rendering
    # ------------------------------------------------------------------

    def render_markdown(self, report: BudgetReport) -> str:
        """Render a BudgetReport as a markdown string.

        No UI library dependencies. All formatting is plain Python.
        """
        lines: list[str] = []
        lines.extend(self._render_header(report.year, report.month, report.generated_date))
        lines.extend(self._render_summary_table(report))
        lines.append("## Detailed Breakdown\n")
        for line in report.lines:
            lines.extend(self._render_category_detail(line, report))
        lines.extend(self._render_footer(report))
        return "\n".join(lines)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _actual_for_category(
        self,
        cat_name: str,
        spending: dict[tuple[str, str | None], float],
    ) -> tuple[float, dict[str, float]]:
        cat_actual = 0.0
        subcat_actuals: dict[str, float] = {}
        for (spent_cat, spent_subcat), amount in spending.items():
            if spent_cat == cat_name:
                cat_actual += amount
                if spent_subcat:
                    subcat_actuals[spent_subcat] = subcat_actuals.get(spent_subcat, 0.0) + amount
        return cat_actual, subcat_actuals

    @staticmethod
    def _fmt(amount: float) -> str:
        return f"${amount:,.2f}"

    @staticmethod
    def _esc_md(s: str) -> str:
        return s.replace("|", "\\|")

    def _render_header(
        self,
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

    def _render_summary_table(self, report: BudgetReport) -> list[str]:
        lines = [
            "## Budget Summary\n",
            "| Category | Budget | Actual | Remaining | % Used |",
            "|----------|--------|--------|-----------|--------|",
        ]
        for line in report.lines:
            budget_str = self._fmt(line.budget_amount) if line.budget_amount is not None else "—"
            actual_str = self._fmt(line.actual_amount)
            remaining_str = self._fmt(line.remaining) if line.remaining is not None else "—"
            pct_str = f"{line.percent_used:.1f}%" if line.percent_used is not None else "—"
            lines.append(
                f"| {line.category_name} | {budget_str} | {actual_str} | {remaining_str} | {pct_str} |"
            )

        total_pct = report.percent_used
        lines.append(
            f"| **TOTAL** | **{self._fmt(report.total_budgeted)}** | **{self._fmt(report.total_actual)}** | **{self._fmt(report.total_remaining)}** | **{total_pct:.1f}%** |"
        )
        lines.append("")
        return lines

    def _render_category_detail(
        self,
        line: BudgetSummaryLine,
        report: BudgetReport,
    ) -> list[str]:
        if line.actual_amount == 0 and line.budget_amount is None:
            return []

        # Look up the full Category object for subcategory list
        cat_obj = self._category_config.find_category(line.category_name)
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
            output.append(f"- **Budget:** {self._fmt(line.budget_amount)}")
            output.append(f"- **Actual:** {self._fmt(line.actual_amount)}")
            output.append(f"- **Remaining:** {self._fmt(remaining)}")
            output.append(f"- **% Used:** {pct:.1f}%")
            output.append(f"- **Status:** {status}")
        else:
            output.append(f"- **Actual:** {self._fmt(line.actual_amount)}")

        if report.month is not None:
            txns = report.transactions_by_category.get(line.category_name, [])
            if txns:
                output.append("")
                output.append("| Date | Description | Subcategory | Amount | Account |")
                output.append("|------|-------------|-------------|--------|---------|")
                for detail in txns:
                    output.append(
                        f"| {detail.date_str} | {self._esc_md(detail.description)} | {self._esc_md(detail.subcategory)} | {self._fmt(detail.amount)} | {self._esc_md(detail.account_id)} |"
                    )
        elif cat_obj and cat_obj.subcategories and line.subcategory_actuals:
            output.append("\n**Subcategories:**\n")
            for subcat in cat_obj.subcategories:
                subcat_actual = line.subcategory_actuals.get(subcat.name, 0.0)
                if subcat_actual > 0:
                    pct_of_cat = (
                        (subcat_actual / line.actual_amount * 100) if line.actual_amount > 0 else 0
                    )
                    output.append(
                        f"- {subcat.name}: {self._fmt(subcat_actual)} ({pct_of_cat:.1f}% of category)"
                    )

        output.append("")
        return output

    def _render_footer(self, report: BudgetReport) -> list[str]:
        lines = [
            "---\n",
            "## Summary\n",
            f"- **Total Budgeted:** {self._fmt(report.total_budgeted)}",
            f"- **Total Actual:** {self._fmt(report.total_actual)}",
            f"- **Total Remaining:** {self._fmt(report.total_remaining)}",
            f"- **Overall % Used:** {report.percent_used:.1f}%",
        ]
        if report.over_budget_count > 0:
            n = report.over_budget_count
            cat_word = "category" if n == 1 else "categories"
            lines.append(f"\n⚠️ **{n} {cat_word} over budget**")
        return lines


__all__ = [
    "BudgetReport",
    "BudgetReportingService",
    "BudgetSummaryLine",
    "ExpenseDetail",
]
