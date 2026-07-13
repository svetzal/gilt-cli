from __future__ import annotations

"""
Tests for categories command.
"""

from gilt.cli.command.categories import run
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.model.category_io import save_categories_config
from gilt.testing import make_group, make_workspace, write_ledger


class DescribeCategoriesCommand:
    """Tests for categories command."""

    def it_should_display_message_when_no_categories_defined(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir", "categories_config"])
        save_categories_config(workspace.categories_config, CategoryConfig(categories=[]))

        rc = run(workspace=workspace)
        assert rc == 0

    def it_should_list_categories_without_usage(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir", "categories_config"])
        config = CategoryConfig(
            categories=[
                Category(name="Housing", description="Housing expenses"),
                Category(name="Transportation", description="Vehicle expenses"),
            ]
        )
        save_categories_config(workspace.categories_config, config)

        rc = run(workspace=workspace)
        assert rc == 0

    def it_should_list_categories_with_usage_statistics(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir", "categories_config"])
        config = CategoryConfig(
            categories=[
                Category(
                    name="Housing",
                    description="Housing expenses",
                    budget=Budget(amount=2500.0, period=BudgetPeriod.monthly),
                ),
                Category(name="Transportation"),
            ]
        )
        save_categories_config(workspace.categories_config, config)

        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-01-01",
                description="Rent Payment",
                amount=-2000.0,
                account_id="TEST",
                category="Housing",
            ),
            make_group(
                transaction_id="2222222222222222",
                date="2025-01-02",
                description="Gas",
                amount=-50.0,
                account_id="TEST",
                category="Transportation",
            ),
        ]
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)

        rc = run(workspace=workspace)
        assert rc == 0

    def it_should_handle_categories_with_subcategories(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir", "categories_config"])
        config = CategoryConfig(
            categories=[
                Category(
                    name="Housing",
                    subcategories=[
                        Subcategory(name="Rent"),
                        Subcategory(name="Utilities"),
                    ],
                ),
            ]
        )
        save_categories_config(workspace.categories_config, config)

        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-01-01",
                description="Rent",
                amount=-2000.0,
                account_id="TEST",
                category="Housing",
                subcategory="Rent",
            ),
            make_group(
                transaction_id="2222222222222222",
                date="2025-01-02",
                description="Electric Bill",
                amount=-100.0,
                account_id="TEST",
                category="Housing",
                subcategory="Utilities",
            ),
        ]
        write_ledger(workspace.ledger_data_dir / "TEST.csv", groups)

        rc = run(workspace=workspace)
        assert rc == 0

    def it_should_return_zero_when_config_missing(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        # Note: config file doesn't exist at root/config/categories.yml

        rc = run(workspace=workspace)
        assert rc == 0

    def it_should_handle_missing_data_directory(self, tmp_path):
        workspace = make_workspace(tmp_path, init_dirs=["categories_config"])
        # Note: data/accounts directory doesn't exist

        config = CategoryConfig(categories=[Category(name="Housing")])
        save_categories_config(workspace.categories_config, config)

        rc = run(workspace=workspace)
        assert rc == 0
