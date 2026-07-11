from __future__ import annotations

"""
Specs for budget_report_markdown — Markdown serialization of BudgetReport.

Tests exercise dump_budget_report_markdown directly; no service instance needed.
"""

from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.services.budget_report_markdown import dump_budget_report_markdown
from gilt.services.budget_reporting_service import BudgetReportingService
from gilt.testing.fixtures import make_transaction


def _make_service(categories: list[Category] | None = None) -> BudgetReportingService:
    config = CategoryConfig(categories=categories or [])
    return BudgetReportingService(category_config=config)


class DescribeMarkdownRendering:
    def it_should_generate_summary_table(self):
        categories = [
            Category(
                name="Groceries",
                budget=Budget(amount=500.00, period=BudgetPeriod.monthly),
            ),
        ]
        service = _make_service(categories)
        transactions = [
            make_transaction(
                transaction_id="t1",
                date="2025-10-10",
                amount=-300.00,
                category="Groceries",
            ),
        ]
        report = service.build_report(transactions, year=2025, month=10)
        markdown = dump_budget_report_markdown(report)
        assert "## Budget Summary" in markdown
        assert "| Category | Budget | Actual | Remaining | % Used |" in markdown
        assert "Groceries" in markdown
        assert "$500.00" in markdown
        assert "$300.00" in markdown

    def it_should_include_detailed_breakdown(self):
        categories = [
            Category(
                name="Transportation",
                description="Vehicle and transit expenses",
                budget=Budget(amount=800.00, period=BudgetPeriod.monthly),
                subcategories=[
                    Subcategory(name="Fuel"),
                ],
            ),
        ]
        service = _make_service(categories)
        transactions = [
            make_transaction(
                transaction_id="t1",
                date="2025-10-01",
                description="Fuel Station",
                amount=-200.00,
                category="Transportation",
                subcategory="Fuel",
            ),
        ]
        report = service.build_report(transactions, year=2025, month=10)
        markdown = dump_budget_report_markdown(report)
        assert "## Detailed Breakdown" in markdown
        assert "### Transportation" in markdown
        assert "Vehicle and transit expenses" in markdown
        # Monthly report should include transaction table
        assert "| Date | Description | Subcategory | Amount | Account |" in markdown
        assert "Fuel Station" in markdown

    def it_should_show_over_budget_warning(self):
        categories = [
            Category(
                name="Groceries",
                budget=Budget(amount=200.00, period=BudgetPeriod.monthly),
            ),
        ]
        service = _make_service(categories)
        transactions = [
            make_transaction(
                transaction_id="t1",
                date="2025-10-01",
                amount=-300.00,  # over budget
                category="Groceries",
            ),
        ]
        report = service.build_report(transactions, year=2025, month=10)
        markdown = dump_budget_report_markdown(report)
        assert "⚠️" in markdown
        assert "over budget" in markdown.lower()

    def it_should_include_report_header_with_period(self):
        service = _make_service()
        transactions: list = []
        report = service.build_report(transactions, year=2025, month=10)
        markdown = dump_budget_report_markdown(report)
        assert "# Budget Report - 2025-10" in markdown
        assert "**Period:**" in markdown
        assert "**Generated:**" in markdown

    def it_should_not_import_rich_or_typer(self):
        """Markdown module must not depend on UI libraries."""
        import gilt.services.budget_report_markdown as mod

        source = mod.__file__
        assert source is not None
        with open(source) as f:
            content = f.read()
        assert "from rich" not in content
        assert "import rich" not in content
        assert "from typer" not in content
        assert "import typer" not in content
