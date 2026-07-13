from __future__ import annotations

"""
Tests for diagnose_categories command.
"""

from gilt.cli.command.diagnose_categories import run
from gilt.model.category import Category, CategoryConfig, Subcategory
from gilt.testing import build_workspace_with_ledger, make_group, make_workspace, write_ledger


class DescribeDiagnoseCategoriesCommand:
    """Tests for diagnose_categories command."""

    def it_should_report_success_when_all_categories_are_defined(self, tmp_path):
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
        rc = run(workspace=ws)
        assert rc == 0  # No issues found

    def it_should_detect_orphaned_category(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(name="Housing"),
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
                    category="Transportation",  # Not in config
                ),
            ],
            config=config,
        )
        rc = run(workspace=ws)
        assert rc == 1  # Issues found

    def it_should_detect_orphaned_subcategory(self, tmp_path):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Housing",
                    subcategories=[
                        Subcategory(name="Rent"),
                    ],
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
                    subcategory="Rent",  # Defined
                ),
                make_group(
                    group_id="2",
                    transaction_id="2222222222222222",
                    date="2025-01-02",
                    description="Electric",
                    amount=-100.0,
                    account_id="TEST",
                    category="Housing",
                    subcategory="Utilities",  # Not defined
                ),
            ],
            config=config,
        )
        rc = run(workspace=ws)
        assert rc == 1  # Issues found

    def it_should_detect_category_used_without_subcategory_when_only_subcategories_defined(
        self, tmp_path
    ):
        config = CategoryConfig(
            categories=[
                Category(
                    name="Housing",
                    subcategories=[
                        Subcategory(name="Rent"),
                    ],
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
                    description="Something",
                    amount=-100.0,
                    account_id="TEST",
                    category="Housing",
                    # No subcategory - but category allows it
                ),
            ],
            config=config,
        )
        # Category without subcategory is always valid if category exists
        rc = run(workspace=ws)
        assert rc == 0  # No issues (category alone is valid)

    def it_should_handle_no_categories_in_config(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Test",
                    amount=-100.0,
                    account_id="TEST",
                    category="Housing",
                ),
            ],
            config=CategoryConfig(categories=[]),
        )
        rc = run(workspace=ws)
        assert rc == 0  # Returns 0 because nothing to compare against

    def it_should_handle_no_categorized_transactions(self, tmp_path):
        config = CategoryConfig(categories=[Category(name="Housing")])
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Test",
                    amount=-100.0,
                    account_id="TEST",
                    # No category
                ),
            ],
            config=config,
        )
        rc = run(workspace=ws)
        assert rc == 0  # No categorized transactions to check

    def it_should_handle_missing_config_file(self, tmp_path):
        # Note: config file doesn't exist at root/config/categories.yml
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Test",
                    amount=-100.0,
                    account_id="TEST",
                    category="Housing",
                ),
            ],
        )
        rc = run(workspace=ws)
        assert rc == 0  # No config to compare against

    def it_should_handle_empty_data_directory(self, tmp_path):
        config = CategoryConfig(categories=[Category(name="Housing")])
        ws = build_workspace_with_ledger(tmp_path, config=config)
        rc = run(workspace=ws)
        assert rc == 0  # No transactions to check

    def it_should_count_orphaned_category_usage(self, tmp_path):
        config = CategoryConfig(categories=[Category(name="Housing")])
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Gas 1",
                    amount=-50.0,
                    account_id="TEST",
                    category="Transportation",
                ),
                make_group(
                    group_id="2",
                    transaction_id="2222222222222222",
                    date="2025-01-02",
                    description="Gas 2",
                    amount=-60.0,
                    account_id="TEST",
                    category="Transportation",
                ),
                make_group(
                    group_id="3",
                    transaction_id="3333333333333333",
                    date="2025-01-03",
                    description="Gas 3",
                    amount=-55.0,
                    account_id="TEST",
                    category="Transportation",
                ),
            ],
            config=config,
        )
        rc = run(workspace=ws)
        assert rc == 1  # Issues found (should show count=3)

    def it_should_handle_multiple_orphaned_categories(self, tmp_path):
        config = CategoryConfig(categories=[Category(name="Housing")])
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    group_id="1",
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Gas",
                    amount=-50.0,
                    account_id="TEST",
                    category="Transportation",
                ),
                make_group(
                    group_id="2",
                    transaction_id="2222222222222222",
                    date="2025-01-02",
                    description="Food",
                    amount=-100.0,
                    account_id="TEST",
                    category="Groceries",
                ),
                make_group(
                    group_id="3",
                    transaction_id="3333333333333333",
                    date="2025-01-03",
                    description="Movie",
                    amount=-20.0,
                    account_id="TEST",
                    category="Entertainment",
                ),
            ],
            config=config,
        )
        rc = run(workspace=ws)
        assert rc == 1  # Issues found (3 orphaned categories)
