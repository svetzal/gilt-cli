from __future__ import annotations

"""
Tests for categorize command.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from finance.cli.command.categorize import run
from finance.model.category import Category, CategoryConfig, Subcategory
from finance.model.category_io import save_categories_config
from finance.model.account import Transaction, TransactionGroup
from finance.model.ledger_io import dump_ledger_csv, load_ledger_csv


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write ledger CSV."""
    csv_text = dump_ledger_csv(groups)
    path.write_text(csv_text, encoding="utf-8")


class DescribeCategorizeValidation:
    """Tests for categorize command validation."""

    def it_should_require_exactly_one_mode(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)
            
            # No mode specified
            rc = run(
                category="Housing",
                config=config_path,
                data_dir=data_dir,
                write=False,
            )
            assert rc == 1
            
            # Multiple modes
            rc = run(
                txid="abcd1234",
                description="Test",
                category="Housing",
                config=config_path,
                data_dir=data_dir,
                write=False,
            )
            assert rc == 1

    def it_should_error_on_nonexistent_category(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            save_categories_config(config_path, CategoryConfig(categories=[]))
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="abcd1234abcd1234",
                        date="2025-01-01",
                        description="Test",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(
                account="TEST",
                txid="abcd1234",
                category="NonExistent",
                config=config_path,
                data_dir=data_dir,
                write=False,
            )
            assert rc == 1


class DescribeCategorizeSingleMode:
    """Tests for single transaction categorization."""

    def it_should_categorize_single_transaction_by_txid(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="abcd1234abcd1234",
                        date="2025-01-01",
                        description="Rent",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Dry-run should not modify
            rc = run(
                account="TEST",
                txid="abcd1234",
                category="Housing",
                config=config_path,
                data_dir=data_dir,
                write=False,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category is None
            
            # Write should categorize
            rc = run(
                account="TEST",
                txid="abcd1234",
                category="Housing",
                config=config_path,
                data_dir=data_dir,
                write=True,
                assume_yes=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Housing"

    def it_should_categorize_with_subcategory(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            from finance.model.category import Subcategory
            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        subcategories=[Subcategory(name="Rent")],
                    )
                ]
            )
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="abcd1234abcd1234",
                        date="2025-01-01",
                        description="Rent",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Using colon syntax
            rc = run(
                account="TEST",
                txid="abcd1234",
                category="Housing",
                subcategory="Rent",
                config=config_path,
                data_dir=data_dir,
                write=True,
                assume_yes=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Housing"
            assert groups[0].primary.subcategory == "Rent"

    def it_should_error_on_ambiguous_txid(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="abcd1234abcd1234",
                        date="2025-01-01",
                        description="Rent 1",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="abcd1234eeeeeeee",
                        date="2025-01-02",
                        description="Rent 2",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(
                txid="abcd1234",  # No account specified, ambiguous
                category="Housing",
                config=config_path,
                data_dir=data_dir,
                write=False,
            )
            assert rc == 1


class DescribeCategorizeBatchMode:
    """Tests for batch categorization."""

    def it_should_categorize_by_exact_description(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Entertainment")])
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="SPOTIFY",
                        amount=-9.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-02-01",
                        description="SPOTIFY",
                        amount=-9.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-03-01",
                        description="NETFLIX",
                        amount=-15.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(
                account="TEST",
                description="SPOTIFY",
                category="Entertainment",
                config=config_path,
                data_dir=data_dir,
                write=True,
                assume_yes=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Entertainment"
            assert groups[1].primary.category == "Entertainment"
            assert groups[2].primary.category is None  # Different description

    def it_should_categorize_by_description_prefix(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Shopping")])
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="AMAZON.COM ORDER 123",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-02-01",
                        description="AMAZON.CA ORDER 456",
                        amount=-75.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-03-01",
                        description="WALMART",
                        amount=-25.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(
                account="TEST",
                desc_prefix="AMAZON",
                category="Shopping",
                config=config_path,
                data_dir=data_dir,
                write=True,
                assume_yes=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Shopping"
            assert groups[1].primary.category == "Shopping"
            assert groups[2].primary.category is None  # Different prefix

    def it_should_categorize_across_multiple_accounts(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Entertainment")])
            save_categories_config(config_path, config)
            
            # Create two ledgers
            for account in ["ACCOUNT1", "ACCOUNT2"]:
                ledger_path = data_dir / f"{account}.csv"
                groups = [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id=f"{account}1111111111",
                            date="2025-01-01",
                            description="SPOTIFY",
                            amount=-9.99,
                            currency="CAD",
                            account_id=account,
                        ),
                    ),
                ]
                _write_ledger(ledger_path, groups)
            
            # No account specified - should categorize in all accounts
            rc = run(
                description="SPOTIFY",
                category="Entertainment",
                config=config_path,
                data_dir=data_dir,
                write=True,
                assume_yes=True,
            )
            assert rc == 0
            
            # Verify both accounts updated
            for account in ["ACCOUNT1", "ACCOUNT2"]:
                ledger_path = data_dir / f"{account}.csv"
                groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
                assert groups[0].primary.category == "Entertainment"

    def it_should_filter_by_amount_in_batch_mode(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Banking")])
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Monthly Fee",
                        amount=-12.95,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-02-01",
                        description="Monthly Fee",
                        amount=-15.00,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Only categorize the -12.95 fee
            rc = run(
                account="TEST",
                description="Monthly Fee",
                amount=-12.95,
                category="Banking",
                config=config_path,
                data_dir=data_dir,
                write=True,
                assume_yes=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Banking"
            assert groups[1].primary.category is None  # Different amount

    def it_should_return_zero_when_no_matches(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="SPOTIFY",
                        amount=-9.99,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(
                account="TEST",
                description="NONEXISTENT",
                category="Housing",
                config=config_path,
                data_dir=data_dir,
                write=False,
            )
            assert rc == 0  # No error, just no matches


class DescribeCategorizeRecategorization:
    """Tests for re-categorization warnings."""

    def it_should_warn_when_recategorizing(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(
                categories=[
                    Category(name="Entertainment"),
                    Category(name="Shopping"),
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
                        description="SPOTIFY",
                        amount=-9.99,
                        currency="CAD",
                        account_id="TEST",
                        category="Entertainment",  # Already categorized
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Should succeed but show warning (check return code is 0)
            rc = run(
                account="TEST",
                description="SPOTIFY",
                category="Shopping",
                config=config_path,
                data_dir=data_dir,
                write=True,
                assume_yes=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Shopping"  # Updated


class DescribeCategorizePatternMode:
    """Tests for pattern matching mode."""

    def it_should_categorize_by_regex_pattern(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Housing", subcategories=[Subcategory(name="Utilities")])])
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Payment - WWW Payment - 12345 HYDRO ONE",
                        amount=-150.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-02-01",
                        description="Payment - WWW Payment - 67890 HYDRO ONE",
                        amount=-145.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-03-01",
                        description="Payment - DIFFERENT VENDOR",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Categorize using regex pattern
            rc = run(
                account="TEST",
                pattern=r"Payment - WWW Payment - \d+ HYDRO ONE",
                category="Housing:Utilities",
                config=config_path,
                data_dir=data_dir,
                write=True,
                assume_yes=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Housing"
            assert groups[0].primary.subcategory == "Utilities"
            assert groups[1].primary.category == "Housing"
            assert groups[1].primary.subcategory == "Utilities"
            assert groups[2].primary.category is None  # Different pattern

    def it_should_error_on_invalid_regex_pattern(self):
        with TemporaryDirectory() as tmpdir:
            config_path = Path(tmpdir) / "categories.yml"
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Test",
                        amount=-10.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Invalid regex should return error code
            rc = run(
                account="TEST",
                pattern=r"[invalid(regex",  # Unclosed bracket
                category="Housing",
                config=config_path,
                data_dir=data_dir,
                write=False,
            )
            assert rc == 1  # Error code for invalid pattern
