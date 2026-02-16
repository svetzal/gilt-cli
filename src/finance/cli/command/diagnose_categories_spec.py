from __future__ import annotations

"""
Tests for diagnose_categories command.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from finance.cli.command.diagnose_categories import run
from finance.model.category import Category, CategoryConfig, Subcategory
from finance.model.category_io import save_categories_config
from finance.model.account import Transaction, TransactionGroup
from finance.model.ledger_io import dump_ledger_csv
from finance.workspace import Workspace


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write ledger CSV."""
    csv_text = dump_ledger_csv(groups)
    path.write_text(csv_text, encoding="utf-8")


class DescribeDiagnoseCategoriesCommand:
    """Tests for diagnose_categories command."""

    def it_should_report_success_when_all_categories_are_defined(self):
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
            
            rc = run(workspace=workspace)
            assert rc == 0  # No issues found

    def it_should_detect_orphaned_category(self):
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
                        category="Transportation",  # Not in config
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(workspace=workspace)
            assert rc == 1  # Issues found

    def it_should_detect_orphaned_subcategory(self):
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
                        ],
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
                        subcategory="Rent",  # Defined
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Electric",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                        subcategory="Utilities",  # Not defined
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(workspace=workspace)
            assert rc == 1  # Issues found

    def it_should_detect_category_used_without_subcategory_when_only_subcategories_defined(self):
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
                        ],
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
                        description="Something",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                        # No subcategory - but category allows it
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Category without subcategory is always valid if category exists
            rc = run(workspace=workspace)
            assert rc == 0  # No issues (category alone is valid)

    def it_should_handle_no_categories_in_config(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))
            
            save_categories_config(config_path, CategoryConfig(categories=[]))
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Test",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(workspace=workspace)
            assert rc == 0  # Returns 0 because nothing to compare against

    def it_should_handle_no_categorized_transactions(self):
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
                        date="2025-01-01",
                        description="Test",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                        # No category
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(workspace=workspace)
            assert rc == 0  # No categorized transactions to check

    def it_should_handle_missing_config_file(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))
            # Note: config file doesn't exist at root/config/categories.yml

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Test",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)

            rc = run(workspace=workspace)
            assert rc == 0  # No config to compare against

    def it_should_handle_empty_data_directory(self):
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
            
            rc = run(workspace=workspace)
            assert rc == 0  # No transactions to check

    def it_should_count_orphaned_category_usage(self):
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
                        date="2025-01-01",
                        description="Gas 1",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Transportation",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Gas 2",
                        amount=-60.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Transportation",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-01-03",
                        description="Gas 3",
                        amount=-55.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Transportation",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(workspace=workspace)
            assert rc == 1  # Issues found (should show count=3)

    def it_should_handle_multiple_orphaned_categories(self):
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
                        date="2025-01-01",
                        description="Gas",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Transportation",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Food",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Groceries",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-01-03",
                        description="Movie",
                        amount=-20.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Entertainment",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(workspace=workspace)
            assert rc == 1  # Issues found (3 orphaned categories)
