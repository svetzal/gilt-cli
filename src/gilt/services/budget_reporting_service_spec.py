from __future__ import annotations

"""
Specs for BudgetReportingService.build_report — report assembly from transactions.

Aggregation, proration, and rendering are tested in their own spec files:
  budget_aggregation_spec.py
  budget_report_markdown_spec.py
"""

from datetime import date

from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.services.budget_reporting_service import BudgetReportingService
from gilt.testing.fixtures import make_transaction


def _make_service(categories: list[Category] | None = None) -> BudgetReportingService:
    config = CategoryConfig(categories=categories or [])
    return BudgetReportingService(category_config=config)


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
        report = service.build_report(transactions, year=2025, month=10)
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
        report = service.build_report(transactions, year=2025, month=10)
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
        report = service.build_report(transactions, year=2025, month=10)
        assert report.total_budgeted == 500.00
        assert report.total_actual == 300.00
        assert report.total_remaining == 200.00

    def it_should_populate_subcategory_order_from_config(self):
        categories = [
            Category(
                name="Transportation",
                budget=Budget(amount=800.00, period=BudgetPeriod.yearly),
                subcategories=[
                    Subcategory(name="Fuel"),
                    Subcategory(name="Insurance"),
                    Subcategory(name="Maintenance"),
                ],
            ),
        ]
        service = _make_service(categories)
        transactions = [
            make_transaction(
                transaction_id="t1",
                date="2025-03-01",
                amount=-100.00,
                category="Transportation",
                subcategory="Fuel",
            ),
            make_transaction(
                transaction_id="t2",
                date="2025-03-15",
                amount=-200.00,
                category="Transportation",
                subcategory="Maintenance",
            ),
        ]
        report = service.build_report(transactions, year=2025, month=None)
        line = report.lines[0]
        assert line.subcategory_order == ["Fuel", "Insurance", "Maintenance"]
