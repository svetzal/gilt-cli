from __future__ import annotations

"""
Tests for categories command.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.categories import run
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.model.category_io import save_categories_config
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.ledger_io import dump_ledger_csv
from gilt.workspace import Workspace


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write ledger CSV."""
    csv_text = dump_ledger_csv(groups)
    path.write_text(csv_text, encoding="utf-8")


class DescribeCategoriesCommand:
    """Tests for categories command."""

    def it_should_display_message_when_no_categories_defined(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Empty config
            save_categories_config(config_path, CategoryConfig(categories=[]))

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_list_categories_without_usage(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create config with categories
            config = CategoryConfig(
                categories=[
                    Category(name="Housing", description="Housing expenses"),
                    Category(name="Transportation", description="Vehicle expenses"),
                ]
            )
            save_categories_config(config_path, config)

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_list_categories_with_usage_statistics(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create config with categories
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
            save_categories_config(config_path, config)

            # Create ledger with categorized transactions
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Rent Payment",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Gas",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Transportation",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_handle_categories_with_subcategories(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create config with categories and subcategories
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
            save_categories_config(config_path, config)

            # Create ledger with subcategorized transactions
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Rent",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                        subcategory="Rent",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Electric Bill",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                        subcategory="Utilities",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_return_zero_when_config_missing(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))
            # Note: config file doesn't exist at root/config/categories.yml

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_handle_missing_data_directory(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            workspace = Workspace(root=Path(tmpdir))
            # Note: data/accounts directory doesn't exist

            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)

            rc = run(workspace=workspace)
            assert rc == 0
