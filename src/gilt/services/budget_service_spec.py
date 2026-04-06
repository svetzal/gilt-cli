from __future__ import annotations

"""
Specs for BudgetService — budget vs actual calculations.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.conftest import write_ledger
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.model.category_io import save_categories_config
from gilt.services.budget_service import BudgetService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_transaction(
    *,
    transaction_id: str,
    txn_date: str,
    description: str,
    amount: float,
    account_id: str = "MYBANK_CHQ",
    category: str | None = None,
    subcategory: str | None = None,
) -> TransactionGroup:
    return TransactionGroup(
        group_id=transaction_id,
        primary=Transaction(
            transaction_id=transaction_id,
            date=txn_date,
            description=description,
            amount=amount,
            currency="CAD",
            account_id=account_id,
            category=category,
            subcategory=subcategory,
        ),
    )


# ---------------------------------------------------------------------------
# get_spending_by_category
# ---------------------------------------------------------------------------


class DescribeGetSpendingByCategory:
    """Specs for spending aggregation by category."""

    def it_should_return_empty_dict_when_no_ledger_files_exist(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            result = service.get_spending_by_category(year=2025, month=1)
            assert result == {}

    def it_should_aggregate_negative_amounts_as_spending(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            groups = [
                _make_transaction(
                    transaction_id="aaaa0001aaaa0001",
                    txn_date="2025-03-10",
                    description="EXAMPLE UTILITY",
                    amount=-150.0,
                    category="Housing",
                ),
                _make_transaction(
                    transaction_id="aaaa0002aaaa0002",
                    txn_date="2025-03-15",
                    description="SAMPLE STORE",
                    amount=-50.0,
                    category="Housing",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            result = service.get_spending_by_category(year=2025, month=3)
            assert result.get("Housing", 0.0) == pytest.approx(200.0)

    def it_should_ignore_positive_amounts(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            groups = [
                _make_transaction(
                    transaction_id="bbbb0001bbbb0001",
                    txn_date="2025-01-05",
                    description="Payroll deposit",
                    amount=3000.0,  # positive income — not an expense
                    category="Income",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            result = service.get_spending_by_category(year=2025, month=1)
            assert result.get("Income", 0.0) == 0.0

    def it_should_filter_by_year_and_month(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            groups = [
                _make_transaction(
                    transaction_id="cccc0001cccc0001",
                    txn_date="2025-01-10",
                    description="ACME CORP",
                    amount=-30.0,
                    category="Shopping",
                ),
                _make_transaction(
                    transaction_id="cccc0002cccc0002",
                    txn_date="2025-02-10",
                    description="ACME CORP",
                    amount=-40.0,
                    category="Shopping",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            jan_result = service.get_spending_by_category(year=2025, month=1)
            feb_result = service.get_spending_by_category(year=2025, month=2)
            assert jan_result.get("Shopping", 0.0) == pytest.approx(30.0)
            assert feb_result.get("Shopping", 0.0) == pytest.approx(40.0)

    def it_should_skip_uncategorized_transactions(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            groups = [
                _make_transaction(
                    transaction_id="dddd0001dddd0001",
                    txn_date="2025-04-01",
                    description="SAMPLE STORE",
                    amount=-25.0,
                    category=None,  # uncategorized
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            result = service.get_spending_by_category(year=2025, month=4)
            assert result == {}


# ---------------------------------------------------------------------------
# get_total_spending
# ---------------------------------------------------------------------------


class DescribeGetTotalSpending:
    """Specs for total spending aggregation."""

    def it_should_sum_all_category_spending(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            groups = [
                _make_transaction(
                    transaction_id="eeee0001eeee0001",
                    txn_date="2025-05-10",
                    description="EXAMPLE UTILITY",
                    amount=-100.0,
                    category="Housing",
                ),
                _make_transaction(
                    transaction_id="eeee0002eeee0002",
                    txn_date="2025-05-20",
                    description="ACME CORP",
                    amount=-60.0,
                    category="Shopping",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            total = service.get_total_spending(year=2025, month=5)
            assert total == pytest.approx(160.0)

    def it_should_return_zero_with_no_transactions(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            total = service.get_total_spending(year=2025, month=1)
            assert total == 0.0


# ---------------------------------------------------------------------------
# get_uncategorized_count
# ---------------------------------------------------------------------------


class DescribeGetUncategorizedCount:
    """Specs for counting uncategorized transactions."""

    def it_should_count_transactions_with_no_category(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            groups = [
                _make_transaction(
                    transaction_id="ffff0001ffff0001",
                    txn_date="2025-06-01",
                    description="SAMPLE STORE",
                    amount=-25.0,
                    category=None,
                ),
                _make_transaction(
                    transaction_id="ffff0002ffff0002",
                    txn_date="2025-06-02",
                    description="ACME CORP",
                    amount=-50.0,
                    category="Shopping",  # categorized
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            count = service.get_uncategorized_count()
            assert count == 1

    def it_should_return_zero_when_all_categorized(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)
            save_categories_config(cats_path, CategoryConfig(categories=[]))

            groups = [
                _make_transaction(
                    transaction_id="gggg0001gggg0001",
                    txn_date="2025-06-10",
                    description="EXAMPLE UTILITY",
                    amount=-100.0,
                    category="Housing",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            count = service.get_uncategorized_count()
            assert count == 0


# ---------------------------------------------------------------------------
# get_budget_summary — period and prorating
# ---------------------------------------------------------------------------


class DescribeGetBudgetSummary:
    """Specs for budget summary generation."""

    def it_should_default_year_to_current_year_when_both_year_and_month_are_none(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)

            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing", budget=Budget(amount=1000.0, period=BudgetPeriod.monthly)
                    )
                ]
            )
            save_categories_config(cats_path, config)

            # Write a transaction for the current year
            current_year = date.today().year
            groups = [
                _make_transaction(
                    transaction_id="hhhh0001hhhh0001",
                    txn_date=f"{current_year}-01-10",
                    description="EXAMPLE UTILITY",
                    amount=-500.0,
                    category="Housing",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            # No year/month specified — should default to current year
            summary = service.get_budget_summary()
            # actual spending should include the current-year transaction
            assert summary.total_actual == pytest.approx(500.0)

    def it_should_prorate_monthly_budget_to_yearly_report(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)

            # Monthly budget of 1000 → yearly report expects 12000
            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing", budget=Budget(amount=1000.0, period=BudgetPeriod.monthly)
                    )
                ]
            )
            save_categories_config(cats_path, config)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            summary = service.get_budget_summary(year=2025)  # yearly report (no month)
            housing_item = next(i for i in summary.items if i.category_name == "Housing")
            assert housing_item.budget_amount == pytest.approx(12000.0)

    def it_should_prorate_yearly_budget_to_monthly_report(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)

            # Yearly budget of 6000 → monthly report expects 500
            config = CategoryConfig(
                categories=[
                    Category(
                        name="Utilities", budget=Budget(amount=6000.0, period=BudgetPeriod.yearly)
                    )
                ]
            )
            save_categories_config(cats_path, config)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            summary = service.get_budget_summary(year=2025, month=3)
            utilities_item = next(i for i in summary.items if i.category_name == "Utilities")
            assert utilities_item.budget_amount == pytest.approx(500.0)

    def it_should_include_over_budget_categories_in_over_budget_count(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)

            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing", budget=Budget(amount=500.0, period=BudgetPeriod.monthly)
                    )
                ]
            )
            save_categories_config(cats_path, config)

            # Spending exceeds budget
            groups = [
                _make_transaction(
                    transaction_id="iiii0001iiii0001",
                    txn_date="2025-09-05",
                    description="EXAMPLE UTILITY",
                    amount=-600.0,
                    category="Housing",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            summary = service.get_budget_summary(year=2025, month=9)
            assert summary.over_budget_count == 1
            housing_item = next(i for i in summary.items if i.category_name == "Housing")
            assert housing_item.is_over_budget is True

    def it_should_not_count_categories_without_budget_in_total_budgeted(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)

            # Category with no budget
            config = CategoryConfig(
                categories=[
                    Category(name="Misc")  # no budget field
                ]
            )
            save_categories_config(cats_path, config)

            groups = [
                _make_transaction(
                    transaction_id="jjjj0001jjjj0001",
                    txn_date="2025-10-01",
                    description="SAMPLE STORE",
                    amount=-50.0,
                    category="Misc",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            summary = service.get_budget_summary(year=2025, month=10)
            assert summary.total_budgeted == 0.0
            misc_item = next(i for i in summary.items if i.category_name == "Misc")
            assert misc_item.budget_amount is None

    def it_should_include_subcategory_items_in_budget_summary(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)

            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        budget=Budget(amount=2000.0, period=BudgetPeriod.monthly),
                        subcategories=[
                            Subcategory(name="Rent"),
                            Subcategory(name="Utilities"),
                        ],
                    )
                ]
            )
            save_categories_config(cats_path, config)

            groups = [
                _make_transaction(
                    transaction_id="kkkk0001kkkk0001",
                    txn_date="2025-11-01",
                    description="Rent payment",
                    amount=-1500.0,
                    category="Housing",
                    subcategory="Rent",
                ),
                _make_transaction(
                    transaction_id="kkkk0002kkkk0002",
                    txn_date="2025-11-10",
                    description="EXAMPLE UTILITY",
                    amount=-200.0,
                    category="Housing",
                    subcategory="Utilities",
                ),
            ]
            write_ledger(data_dir / "MYBANK_CHQ.csv", groups)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            summary = service.get_budget_summary(year=2025, month=11)

            # There should be header + 2 subcategory rows
            housing_items = [i for i in summary.items if i.category_name == "Housing"]
            assert len(housing_items) == 3  # 1 header + 2 subcategories

            header = next(i for i in housing_items if i.is_category_header)
            assert header.actual_amount == pytest.approx(1700.0)

            rent_item = next(i for i in housing_items if i.subcategory_name == "Rent")
            assert rent_item.actual_amount == pytest.approx(1500.0)

    def it_should_filter_to_requested_category_only(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            cats_path = Path(tmpdir) / "config" / "categories.yml"
            cats_path.parent.mkdir(parents=True)

            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing", budget=Budget(amount=1000.0, period=BudgetPeriod.monthly)
                    ),
                    Category(
                        name="Shopping", budget=Budget(amount=300.0, period=BudgetPeriod.monthly)
                    ),
                ]
            )
            save_categories_config(cats_path, config)

            service = BudgetService(data_dir=data_dir, categories_config=cats_path)
            summary = service.get_budget_summary(year=2025, month=6, category_filter="Housing")

            category_names = {i.category_name for i in summary.items}
            assert "Housing" in category_names
            assert "Shopping" not in category_names


# ---------------------------------------------------------------------------
# pytest import (used via pytest.approx in methods above)
# ---------------------------------------------------------------------------

import pytest  # noqa: E402
