from __future__ import annotations

"""
Specs for BudgetReportingService - pure business logic for budget reports.

All tests use Transaction objects directly — no projections DB, no file I/O.
"""

from datetime import date

from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.services.budget_reporting_service import (
    BudgetReportingService,
    ExpenseDetail,
)
from gilt.testing.fixtures import make_transaction


def _make_service(categories: list[Category] | None = None) -> BudgetReportingService:
    config = CategoryConfig(categories=categories or [])
    return BudgetReportingService(category_config=config)


class DescribeSpendingAggregation:
    def it_should_aggregate_expenses_by_category_and_subcategory(self):
        service = _make_service()
        transactions = [
            make_transaction(
                transaction_id="t1",
                amount=-100.00,
                category="Utilities",
                subcategory="Electric",
            ),
            make_transaction(
                transaction_id="t2",
                amount=-50.00,
                category="Utilities",
                subcategory="Water",
            ),
            make_transaction(
                transaction_id="t3",
                amount=-200.00,
                category="Groceries",
                subcategory=None,
            ),
        ]
        result = service.aggregate_spending(transactions, year=None, month=None)
        assert result[("Utilities", "Electric")] == 100.00
        assert result[("Utilities", "Water")] == 50.00
        assert result[("Groceries", None)] == 200.00

    def it_should_skip_transactions_without_category(self):
        service = _make_service()
        transactions = [
            make_transaction(transaction_id="t1", amount=-100.00, category=None),
            make_transaction(transaction_id="t2", amount=-50.00, category="Groceries"),
        ]
        result = service.aggregate_spending(transactions, year=None, month=None)
        assert len(result) == 1
        assert result[("Groceries", None)] == 50.00

    def it_should_filter_by_year(self):
        service = _make_service()
        transactions = [
            make_transaction(
                transaction_id="t1", date="2025-03-01", amount=-100.00, category="Groceries"
            ),
            make_transaction(
                transaction_id="t2", date="2024-03-01", amount=-200.00, category="Groceries"
            ),
        ]
        result = service.aggregate_spending(transactions, year=2025, month=None)
        assert result[("Groceries", None)] == 100.00

    def it_should_filter_by_year_and_month(self):
        service = _make_service()
        transactions = [
            make_transaction(
                transaction_id="t1", date="2025-10-01", amount=-100.00, category="Groceries"
            ),
            make_transaction(
                transaction_id="t2", date="2025-11-01", amount=-200.00, category="Groceries"
            ),
        ]
        result = service.aggregate_spending(transactions, year=2025, month=10)
        assert result[("Groceries", None)] == 100.00
        assert ("Groceries", None) in result
        assert result.get(("Groceries", None), 0) == 100.00

    def it_should_return_empty_dict_for_empty_input(self):
        service = _make_service()
        result = service.aggregate_spending([], year=None, month=None)
        assert result == {}


class DescribeCollectExpenseTransactions:
    def it_should_group_expense_transactions_by_category(self):
        service = _make_service()
        transactions = [
            make_transaction(
                transaction_id="t1",
                date="2025-10-01",
                description="EXAMPLE UTILITY",
                amount=-100.00,
                category="Utilities",
                subcategory="Electric",
            ),
            make_transaction(
                transaction_id="t2",
                date="2025-10-05",
                description="SAMPLE STORE",
                amount=-50.00,
                category="Groceries",
            ),
        ]
        result = service.collect_expense_transactions(transactions, year=None, month=None)
        assert "Utilities" in result
        assert "Groceries" in result
        assert len(result["Utilities"]) == 1
        assert isinstance(result["Utilities"][0], ExpenseDetail)
        assert result["Utilities"][0].description == "EXAMPLE UTILITY"
        assert result["Utilities"][0].amount == 100.00
        assert result["Utilities"][0].subcategory == "Electric"

    def it_should_exclude_income_transactions(self):
        service = _make_service()
        transactions = [
            make_transaction(
                transaction_id="t1",
                amount=500.00,  # positive = income
                category="Income",
            ),
            make_transaction(
                transaction_id="t2",
                amount=-100.00,
                category="Groceries",
            ),
        ]
        result = service.collect_expense_transactions(transactions, year=None, month=None)
        assert "Income" not in result
        assert "Groceries" in result

    def it_should_sort_transactions_deterministically(self):
        service = _make_service()
        transactions = [
            make_transaction(
                transaction_id="t3",
                date="2025-10-05",
                description="Beta",
                amount=-30.00,
                category="Groceries",
            ),
            make_transaction(
                transaction_id="t1",
                date="2025-10-01",
                description="Alpha",
                amount=-10.00,
                category="Groceries",
            ),
            make_transaction(
                transaction_id="t2",
                date="2025-10-01",
                description="Gamma",
                amount=-20.00,
                category="Groceries",
            ),
        ]
        result = service.collect_expense_transactions(transactions, year=None, month=None)
        items = result["Groceries"]
        # First: 2025-10-01, amount 10.00 (smallest), description Alpha
        # Second: 2025-10-01, amount 20.00, description Gamma
        # Third: 2025-10-05, amount 30.00, description Beta
        assert items[0].date_str == "2025-10-01"
        assert items[0].amount == 10.00
        assert items[1].date_str == "2025-10-01"
        assert items[1].amount == 20.00
        assert items[2].date_str == "2025-10-05"


class DescribeBudgetForPeriod:
    def it_should_return_monthly_amount_for_monthly_budget_in_monthly_report(self):
        service = _make_service()
        budget = Budget(amount=500.00, period=BudgetPeriod.monthly)
        result = service.budget_for_period(budget, month=10)
        assert result == 500.00

    def it_should_prorate_yearly_budget_to_monthly(self):
        service = _make_service()
        budget = Budget(amount=1200.00, period=BudgetPeriod.yearly)
        result = service.budget_for_period(budget, month=10)
        assert result == 100.00

    def it_should_return_yearly_amount_for_yearly_budget_in_yearly_report(self):
        service = _make_service()
        budget = Budget(amount=1200.00, period=BudgetPeriod.yearly)
        result = service.budget_for_period(budget, month=None)
        assert result == 1200.00

    def it_should_multiply_monthly_budget_to_yearly(self):
        service = _make_service()
        budget = Budget(amount=500.00, period=BudgetPeriod.monthly)
        result = service.budget_for_period(budget, month=None)
        assert result == 6000.00

    def it_should_return_none_when_no_budget(self):
        service = _make_service()
        result = service.budget_for_period(None, month=10)
        assert result is None


class DescribeGenerateReport:
    def it_should_assemble_report_with_all_categories(self):
        categories = [
            Category(
                name="Groceries",
                budget=Budget(amount=500.00, period=BudgetPeriod.monthly),
            ),
            Category(
                name="Utilities",
                budget=Budget(amount=200.00, period=BudgetPeriod.monthly),
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
            make_transaction(
                transaction_id="t2",
                date="2025-10-15",
                amount=-150.00,
                category="Utilities",
            ),
        ]
        report = service.generate_report(transactions, year=2025, month=10)
        assert report.year == 2025
        assert report.month == 10
        assert isinstance(report.generated_date, date)
        assert len(report.lines) == 2
        names = [line.category_name for line in report.lines]
        assert "Groceries" in names
        assert "Utilities" in names

    def it_should_count_over_budget_categories(self):
        categories = [
            Category(
                name="Groceries",
                budget=Budget(amount=200.00, period=BudgetPeriod.monthly),
            ),
            Category(
                name="Utilities",
                budget=Budget(amount=200.00, period=BudgetPeriod.monthly),
            ),
        ]
        service = _make_service(categories)
        transactions = [
            make_transaction(
                transaction_id="t1",
                date="2025-10-01",
                amount=-300.00,
                category="Groceries",  # over budget
            ),
            make_transaction(
                transaction_id="t2",
                date="2025-10-01",
                amount=-100.00,
                category="Utilities",  # under budget
            ),
        ]
        report = service.generate_report(transactions, year=2025, month=10)
        assert report.over_budget_count == 1

    def it_should_calculate_totals(self):
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
                date="2025-10-01",
                amount=-300.00,
                category="Groceries",
            ),
        ]
        report = service.generate_report(transactions, year=2025, month=10)
        assert report.total_budgeted == 500.00
        assert report.total_actual == 300.00
        assert report.total_remaining == 200.00


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
        report = service.generate_report(transactions, year=2025, month=10)
        markdown = service.render_markdown(report)
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
        report = service.generate_report(transactions, year=2025, month=10)
        markdown = service.render_markdown(report)
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
        report = service.generate_report(transactions, year=2025, month=10)
        markdown = service.render_markdown(report)
        assert "⚠️" in markdown
        assert "over budget" in markdown.lower()

    def it_should_include_report_header_with_period(self):
        service = _make_service()
        transactions: list = []
        report = service.generate_report(transactions, year=2025, month=10)
        markdown = service.render_markdown(report)
        assert "# Budget Report - 2025-10" in markdown
        assert "**Period:**" in markdown
        assert "**Generated:**" in markdown

    def it_should_not_import_rich_or_typer(self):
        """Service module must not depend on UI libraries."""
        import gilt.services.budget_reporting_service as mod

        source = mod.__file__
        assert source is not None
        with open(source) as f:
            content = f.read()
        assert "from rich" not in content
        assert "import rich" not in content
        assert "from typer" not in content
        assert "import typer" not in content
