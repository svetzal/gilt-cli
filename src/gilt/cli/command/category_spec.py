from __future__ import annotations

"""
Tests for category command.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.category import run
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.model.category_io import load_categories_config, save_categories_config
from gilt.model.ledger_io import dump_ledger_csv
from gilt.workspace import Workspace


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write ledger CSV."""
    csv_text = dump_ledger_csv(groups)
    path.write_text(csv_text, encoding="utf-8")


class DescribeCategoryAdd:
    """Tests for category --add command."""

    def it_should_add_new_category_with_write(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Start with empty config
            save_categories_config(config_path, CategoryConfig(categories=[]))

            # Dry-run should not modify
            rc = run(
                add="Housing",
                description="Housing expenses",
                workspace=workspace,
                write=False,
            )
            assert rc == 0
            config = load_categories_config(config_path)
            assert len(config.categories) == 0

            # Write should add category
            rc = run(
                add="Housing",
                description="Housing expenses",
                workspace=workspace,
                write=True,
            )
            assert rc == 0
            config = load_categories_config(config_path)
            assert len(config.categories) == 1
            assert config.categories[0].name == "Housing"
            assert config.categories[0].description == "Housing expenses"

    def it_should_add_subcategory_to_existing_category(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # Create parent category
            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)

            # Add subcategory
            rc = run(
                add="Housing:Utilities",
                description="Electric, gas, water",
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            config = load_categories_config(config_path)
            assert len(config.categories) == 1
            assert len(config.categories[0].subcategories) == 1
            assert config.categories[0].subcategories[0].name == "Utilities"

    def it_should_error_when_adding_subcategory_without_parent(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            save_categories_config(config_path, CategoryConfig(categories=[]))

            rc = run(
                add="Housing:Utilities",
                workspace=workspace,
                write=True,
            )
            assert rc == 1

    def it_should_skip_when_category_already_exists(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)

            rc = run(
                add="Housing",
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            # Should still have only one category
            config = load_categories_config(config_path)
            assert len(config.categories) == 1


class DescribeCategoryRemove:
    """Tests for category --remove command."""

    def it_should_remove_category_with_write(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(
                categories=[
                    Category(name="Housing"),
                    Category(name="Transportation"),
                ]
            )
            save_categories_config(config_path, config)

            # Dry-run should not modify
            rc = run(
                remove="Housing",
                workspace=workspace,
                write=False,
            )
            assert rc == 0
            config = load_categories_config(config_path)
            assert len(config.categories) == 2

            # Write with force should remove
            rc = run(
                remove="Housing",
                force=True,
                workspace=workspace,
                write=True,
            )
            assert rc == 0
            config = load_categories_config(config_path)
            assert len(config.categories) == 1
            assert config.categories[0].name == "Transportation"

    def it_should_remove_subcategory(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

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

            rc = run(
                remove="Housing:Utilities",
                force=True,
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            config = load_categories_config(config_path)
            assert len(config.categories[0].subcategories) == 1
            assert config.categories[0].subcategories[0].name == "Rent"

    def it_should_require_force_when_category_is_used(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)

            # Create ledger with categorized transaction
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
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)

            # Without force should fail in dry-run
            rc = run(
                remove="Housing",
                workspace=workspace,
                write=False,
            )
            assert rc == 1

            # With force should succeed
            rc = run(
                remove="Housing",
                force=True,
                workspace=workspace,
                write=True,
            )
            assert rc == 0


class DescribeCategorySetBudget:
    """Tests for category --set-budget command."""

    def it_should_set_budget_for_category(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Dining Out")])
            save_categories_config(config_path, config)

            # Dry-run should not modify
            rc = run(
                set_budget="Dining Out",
                amount=400.0,
                period="monthly",
                workspace=workspace,
                write=False,
            )
            assert rc == 0
            config = load_categories_config(config_path)
            assert config.categories[0].budget is None

            # Write should set budget
            rc = run(
                set_budget="Dining Out",
                amount=400.0,
                period="monthly",
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            config = load_categories_config(config_path)
            assert config.categories[0].budget is not None
            assert config.categories[0].budget.amount == 400.0
            assert config.categories[0].budget.period == BudgetPeriod.monthly

    def it_should_update_existing_budget(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(
                categories=[
                    Category(
                        name="Dining Out",
                        budget=Budget(amount=300.0, period=BudgetPeriod.monthly),
                    )
                ]
            )
            save_categories_config(config_path, config)

            rc = run(
                set_budget="Dining Out",
                amount=500.0,
                period="yearly",
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            config = load_categories_config(config_path)
            assert config.categories[0].budget.amount == 500.0
            assert config.categories[0].budget.period == BudgetPeriod.yearly

    def it_should_error_when_setting_budget_for_nonexistent_category(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            save_categories_config(config_path, CategoryConfig(categories=[]))

            rc = run(
                set_budget="NonExistent",
                amount=100.0,
                workspace=workspace,
                write=True,
            )
            assert rc == 1

    def it_should_error_when_setting_budget_for_subcategory(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        subcategories=[Subcategory(name="Utilities")],
                    )
                ]
            )
            save_categories_config(config_path, config)

            rc = run(
                set_budget="Housing:Utilities",
                amount=100.0,
                workspace=workspace,
                write=True,
            )
            assert rc == 1

    def it_should_require_amount_parameter(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)

            rc = run(
                set_budget="Housing",
                amount=None,
                workspace=workspace,
                write=True,
            )
            assert rc == 1

    def it_should_reject_negative_amount(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)

            rc = run(
                set_budget="Housing",
                amount=-100.0,
                workspace=workspace,
                write=True,
            )
            assert rc == 1


class DescribeCategoryValidation:
    """Tests for category command validation."""

    def it_should_require_exactly_one_action(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            # No action
            rc = run(
                workspace=workspace,
                write=False,
            )
            assert rc == 1

            # Multiple actions
            rc = run(
                add="Housing",
                remove="Transportation",
                workspace=workspace,
                write=False,
            )
            assert rc == 1
