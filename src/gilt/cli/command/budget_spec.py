from __future__ import annotations

"""
Tests for budget command.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.budget import run
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from gilt.model.category_io import save_categories_config
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.ledger_io import dump_ledger_csv
from gilt.workspace import Workspace


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write ledger CSV."""
    csv_text = dump_ledger_csv(groups)
    path.write_text(csv_text, encoding="utf-8")


class DescribeBudgetCommand:
    """Tests for budget command."""

    def it_should_display_message_when_no_categories_defined(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            save_categories_config(config_path, CategoryConfig(categories=[]))

            rc = run(workspace=workspace)
            assert rc == 0

    def it_should_show_budget_with_spending(self):
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
                        budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-15",
                        description="Restaurant",
                        amount=-150.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Dining Out",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)

            rc = run(year=2025, workspace=workspace)
            assert rc == 0

    def it_should_filter_by_year(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(
                categories=[Category(name="Housing")]
            )
            save_categories_config(config_path, config)

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2024-01-01",
                        description="Rent 2024",
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
                        date="2025-01-01",
                        description="Rent 2025",
                        amount=-2100.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)

            # Should only include 2025 transaction
            rc = run(year=2025, workspace=workspace)
            assert rc == 0

    def it_should_filter_by_month(self):
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
                        budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-15",
                        description="January",
                        amount=-150.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Dining Out",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-02-15",
                        description="February",
                        amount=-200.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Dining Out",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Should only include January transaction
            rc = run(year=2025, month=1, workspace=workspace)
            assert rc == 0

    def it_should_filter_by_category(self):
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
            
            # Should only show Housing
            rc = run(year=2025, category="Housing", workspace=workspace)
            assert rc == 0

    def it_should_error_when_month_without_year(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))
            
            config = CategoryConfig(
                categories=[Category(name="Housing")]
            )
            save_categories_config(config_path, config)
            
            rc = run(month=1, workspace=workspace)
            assert rc == 1

    def it_should_error_on_invalid_month(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))
            
            config = CategoryConfig(
                categories=[Category(name="Housing")]
            )
            save_categories_config(config_path, config)
            
            rc = run(year=2025, month=13, workspace=workspace)
            assert rc == 1


class DescribeBudgetProration:
    """Tests for budget proration logic."""

    def it_should_use_monthly_budget_for_monthly_report(self):
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
                        budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-15",
                        description="Restaurant",
                        amount=-150.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Dining Out",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Monthly report should use 400.0 budget directly
            rc = run(year=2025, month=1, workspace=workspace)
            assert rc == 0

    def it_should_prorate_yearly_budget_for_monthly_report(self):
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
                        budget=Budget(amount=4800.0, period=BudgetPeriod.yearly),
                    ),
                ]
            )
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-15",
                        description="Restaurant",
                        amount=-150.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Dining Out",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Monthly report should prorate: 4800 / 12 = 400
            rc = run(year=2025, month=1, workspace=workspace)
            assert rc == 0

    def it_should_use_yearly_budget_for_yearly_report(self):
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
                        budget=Budget(amount=4800.0, period=BudgetPeriod.yearly),
                    ),
                ]
            )
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-15",
                        description="Restaurant",
                        amount=-1800.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Dining Out",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Yearly report should use 4800.0 budget directly
            rc = run(year=2025, workspace=workspace)
            assert rc == 0

    def it_should_multiply_monthly_budget_for_yearly_report(self):
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
                        budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-15",
                        description="Restaurant",
                        amount=-1800.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Dining Out",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Yearly report should multiply: 400 * 12 = 4800
            rc = run(year=2025, workspace=workspace)
            assert rc == 0


class DescribeBudgetWithSubcategories:
    """Tests for budget reporting with subcategories."""

    def it_should_aggregate_subcategory_spending_under_parent(self):
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
                        budget=Budget(amount=2500.0, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)
            
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
                        amount=-300.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                        subcategory="Utilities",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Should show parent with total 2300.0 against budget 2500.0
            rc = run(year=2025, workspace=workspace)
            assert rc == 0

    def it_should_show_category_without_budget(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))
            
            config = CategoryConfig(
                categories=[
                    Category(name="Misc"),  # No budget
                ]
            )
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Random",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Misc",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(year=2025, workspace=workspace)
            assert rc == 0

    def it_should_handle_categories_with_no_spending(self):
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
                        budget=Budget(amount=400.0, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = []  # No transactions
            _write_ledger(ledger_path, groups)
            
            rc = run(year=2025, workspace=workspace)
            assert rc == 0
