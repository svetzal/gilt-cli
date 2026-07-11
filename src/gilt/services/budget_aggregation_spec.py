from __future__ import annotations

"""
Specs for budget_aggregation — pure aggregation and budget proration functions.

All tests use Transaction objects directly — no I/O, no projections DB.
"""

from gilt.model.category import Budget, BudgetPeriod
from gilt.services.budget_aggregation import (
    aggregate_spending,
    collect_expense_transactions,
    get_budget_for_period,
)
from gilt.services.budget_report_model import ExpenseDetail
from gilt.testing.fixtures import make_transaction


class DescribeSpendingAggregation:
    def it_should_aggregate_expenses_by_category_and_subcategory(self):
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
        result = aggregate_spending(transactions, year=None, month=None)
        assert result[("Utilities", "Electric")] == 100.00
        assert result[("Utilities", "Water")] == 50.00
        assert result[("Groceries", None)] == 200.00

    def it_should_skip_transactions_without_category(self):
        transactions = [
            make_transaction(transaction_id="t1", amount=-100.00, category=None),
            make_transaction(transaction_id="t2", amount=-50.00, category="Groceries"),
        ]
        result = aggregate_spending(transactions, year=None, month=None)
        assert len(result) == 1
        assert result[("Groceries", None)] == 50.00

    def it_should_filter_by_year(self):
        transactions = [
            make_transaction(
                transaction_id="t1", date="2025-03-01", amount=-100.00, category="Groceries"
            ),
            make_transaction(
                transaction_id="t2", date="2024-03-01", amount=-200.00, category="Groceries"
            ),
        ]
        result = aggregate_spending(transactions, year=2025, month=None)
        assert result[("Groceries", None)] == 100.00

    def it_should_filter_by_year_and_month(self):
        transactions = [
            make_transaction(
                transaction_id="t1", date="2025-10-01", amount=-100.00, category="Groceries"
            ),
            make_transaction(
                transaction_id="t2", date="2025-11-01", amount=-200.00, category="Groceries"
            ),
        ]
        result = aggregate_spending(transactions, year=2025, month=10)
        assert result[("Groceries", None)] == 100.00
        assert ("Groceries", None) in result
        assert result.get(("Groceries", None), 0) == 100.00

    def it_should_return_empty_dict_for_empty_input(self):
        result = aggregate_spending([], year=None, month=None)
        assert result == {}


class DescribeCollectExpenseTransactions:
    def it_should_group_expense_transactions_by_category(self):
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
        result = collect_expense_transactions(transactions, year=None, month=None)
        assert "Utilities" in result
        assert "Groceries" in result
        assert len(result["Utilities"]) == 1
        assert isinstance(result["Utilities"][0], ExpenseDetail)
        assert result["Utilities"][0].description == "EXAMPLE UTILITY"
        assert result["Utilities"][0].amount == 100.00
        assert result["Utilities"][0].subcategory == "Electric"

    def it_should_exclude_income_transactions(self):
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
        result = collect_expense_transactions(transactions, year=None, month=None)
        assert "Income" not in result
        assert "Groceries" in result

    def it_should_sort_transactions_deterministically(self):
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
        result = collect_expense_transactions(transactions, year=None, month=None)
        items = result["Groceries"]
        assert items[0].date_str == "2025-10-01"
        assert items[0].amount == 10.00
        assert items[1].date_str == "2025-10-01"
        assert items[1].amount == 20.00
        assert items[2].date_str == "2025-10-05"


class DescribeBudgetForPeriod:
    def it_should_return_monthly_amount_for_monthly_budget_in_monthly_report(self):
        budget = Budget(amount=500.00, period=BudgetPeriod.monthly)
        result = get_budget_for_period(budget, month=10)
        assert result == 500.00

    def it_should_prorate_yearly_budget_to_monthly(self):
        budget = Budget(amount=1200.00, period=BudgetPeriod.yearly)
        result = get_budget_for_period(budget, month=10)
        assert result == 100.00

    def it_should_return_yearly_amount_for_yearly_budget_in_yearly_report(self):
        budget = Budget(amount=1200.00, period=BudgetPeriod.yearly)
        result = get_budget_for_period(budget, month=None)
        assert result == 1200.00

    def it_should_multiply_monthly_budget_to_yearly(self):
        budget = Budget(amount=500.00, period=BudgetPeriod.monthly)
        result = get_budget_for_period(budget, month=None)
        assert result == 6000.00

    def it_should_return_none_when_no_budget(self):
        result = get_budget_for_period(None, month=10)
        assert result is None
