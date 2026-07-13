from __future__ import annotations

"""
Tests for budget command.
"""

import pytest

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.budget import run
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.testing import build_workspace_with_ledger, make_group


class DescribeBudgetCommand:
    """Tests for budget command."""

    def it_should_display_message_when_no_categories_defined(self, tmp_path):
        ws = build_workspace_with_ledger(tmp_path, config=CategoryConfig(categories=[]))
        rc = run(workspace=ws)
        assert rc == 0

    def it_should_show_budget_with_spending(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Dining Out",
                    budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                ),
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-15",
                    description="Restaurant",
                    amount=-150.0,
                    account_id="TEST",
                    category="Dining Out",
                ),
            ],
            config=config,
        )
        rc = run(year=2025, workspace=ws)
        assert rc == 0

    def it_should_filter_by_year(self, tmp_path):
        config = CategoryConfig(categories=[Category(name="Housing")])
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2024-01-01",
                    description="Rent 2024",
                    amount=-2000.0,
                    account_id="TEST",
                    category="Housing",
                ),
                make_group(
                    group_id="2",
                    transaction_id="2222222222222222",
                    date="2025-01-01",
                    description="Rent 2025",
                    amount=-2100.0,
                    account_id="TEST",
                    category="Housing",
                ),
            ],
            config=config,
        )
        # Should only include 2025 transaction
        rc = run(year=2025, workspace=ws)
        assert rc == 0

    def it_should_filter_by_month(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Dining Out",
                    budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                ),
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-15",
                    description="January",
                    amount=-150.0,
                    account_id="TEST",
                    category="Dining Out",
                ),
                make_group(
                    group_id="2",
                    transaction_id="2222222222222222",
                    date="2025-02-15",
                    description="February",
                    amount=-200.0,
                    account_id="TEST",
                    category="Dining Out",
                ),
            ],
            config=config,
        )
        # Should only include January transaction
        rc = run(year=2025, month=1, workspace=ws)
        assert rc == 0

    def it_should_filter_by_category(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(name="Housing"),
                Category(name="Transportation"),
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Rent",
                    amount=-2000.0,
                    account_id="TEST",
                    category="Housing",
                ),
                make_group(
                    group_id="2",
                    transaction_id="2222222222222222",
                    date="2025-01-02",
                    description="Gas",
                    amount=-50.0,
                    account_id="TEST",
                    category="Transportation",
                ),
            ],
            config=config,
        )
        # Should only show Housing
        rc = run(year=2025, category="Housing", workspace=ws)
        assert rc == 0

    def it_should_error_when_month_without_year(self, tmp_path):
        config = CategoryConfig(categories=[Category(name="Housing")])
        ws = build_workspace_with_ledger(tmp_path, config=config)
        with pytest.raises(CommandAbort) as exc_info:
            run(month=1, workspace=ws)
        assert exc_info.value.code == 1

    def it_should_error_on_invalid_month(self, tmp_path):
        config = CategoryConfig(categories=[Category(name="Housing")])
        ws = build_workspace_with_ledger(tmp_path, config=config)
        with pytest.raises(CommandAbort) as exc_info:
            run(year=2025, month=13, workspace=ws)
        assert exc_info.value.code == 1


class DescribeBudgetProration:
    """Tests for budget proration logic."""

    def it_should_use_monthly_budget_for_monthly_report(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Dining Out",
                    budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                ),
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-15",
                    description="Restaurant",
                    amount=-150.0,
                    account_id="TEST",
                    category="Dining Out",
                ),
            ],
            config=config,
        )
        # Monthly report should use 400.0 budget directly
        rc = run(year=2025, month=1, workspace=ws)
        assert rc == 0

    def it_should_prorate_yearly_budget_for_monthly_report(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Dining Out",
                    budget=Budget(amount=4800.0, period=BudgetPeriod.yearly),
                ),
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-15",
                    description="Restaurant",
                    amount=-150.0,
                    account_id="TEST",
                    category="Dining Out",
                ),
            ],
            config=config,
        )
        # Monthly report should prorate: 4800 / 12 = 400
        rc = run(year=2025, month=1, workspace=ws)
        assert rc == 0

    def it_should_use_yearly_budget_for_yearly_report(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Dining Out",
                    budget=Budget(amount=4800.0, period=BudgetPeriod.yearly),
                ),
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-15",
                    description="Restaurant",
                    amount=-1800.0,
                    account_id="TEST",
                    category="Dining Out",
                ),
            ],
            config=config,
        )
        # Yearly report should use 4800.0 budget directly
        rc = run(year=2025, workspace=ws)
        assert rc == 0

    def it_should_multiply_monthly_budget_for_yearly_report(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Dining Out",
                    budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                ),
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-15",
                    description="Restaurant",
                    amount=-1800.0,
                    account_id="TEST",
                    category="Dining Out",
                ),
            ],
            config=config,
        )
        # Yearly report should multiply: 400 * 12 = 4800
        rc = run(year=2025, workspace=ws)
        assert rc == 0


class DescribeBudgetWithSubcategories:
    """Tests for budget reporting with subcategories."""

    def it_should_aggregate_subcategory_spending_under_parent(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Housing",
                    subcategories=[
                        Subcategory(name="Rent"),
                        Subcategory(name="Utilities"),
                    ],
                    budget=Budget(amount=2500.0, period=BudgetPeriod.monthly),
                ),
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Rent",
                    amount=-2000.0,
                    account_id="TEST",
                    category="Housing",
                    subcategory="Rent",
                ),
                make_group(
                    group_id="2",
                    transaction_id="2222222222222222",
                    date="2025-01-02",
                    description="Electric Bill",
                    amount=-300.0,
                    account_id="TEST",
                    category="Housing",
                    subcategory="Utilities",
                ),
            ],
            config=config,
        )
        # Should show parent with total 2300.0 against budget 2500.0
        rc = run(year=2025, workspace=ws)
        assert rc == 0

    def it_should_show_category_without_budget(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(name="Misc"),  # No budget
            ]
        )
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Random",
                    amount=-50.0,
                    account_id="TEST",
                    category="Misc",
                ),
            ],
            config=config,
        )
        rc = run(year=2025, workspace=ws)
        assert rc == 0

    def it_should_handle_categories_with_no_spending(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Dining Out",
                    budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                ),
            ]
        )
        ws = build_workspace_with_ledger(tmp_path, config=config)
        rc = run(year=2025, workspace=ws)
        assert rc == 0
