from __future__ import annotations

"""
Tests for recategorize command.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from finance.cli.command.recategorize import run
from finance.model.account import Transaction, TransactionGroup
from finance.model.ledger_io import dump_ledger_csv, load_ledger_csv


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write ledger CSV."""
    csv_text = dump_ledger_csv(groups)
    path.write_text(csv_text, encoding="utf-8")


class DescribeRecategorizeCommand:
    """Tests for recategorize command."""

    def it_should_rename_category_preserving_subcategories(self):
        """Test that renaming only the parent category preserves existing subcategories."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Bank Fee",
                        amount=-46.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Business",
                        subcategory="Bank Fees",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Loan Payment",
                        amount=-500.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Business",
                        subcategory="Loan",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-01-03",
                        description="Subscription",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Business",
                        subcategory="Subscriptions",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Dry-run should not modify
            rc = run(
                from_category="Business",
                to_category="Mojility",
                data_dir=data_dir,
                write=False,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Business"
            assert groups[0].primary.subcategory == "Bank Fees"
            
            # Write should rename category but preserve subcategories
            rc = run(
                from_category="Business",
                to_category="Mojility",
                data_dir=data_dir,
                write=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Mojility"
            assert groups[0].primary.subcategory == "Bank Fees"
            assert groups[1].primary.category == "Mojility"
            assert groups[1].primary.subcategory == "Loan"
            assert groups[2].primary.category == "Mojility"
            assert groups[2].primary.subcategory == "Subscriptions"

    def it_should_rename_specific_subcategory(self):
        """Test that specifying both category and subcategory renames only that subcategory."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Bank Fee",
                        amount=-46.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Business",
                        subcategory="Bank Fees",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Loan Payment",
                        amount=-500.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Business",
                        subcategory="Loan",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Rename only Business:Bank Fees to Mojility:Bank Fees
            rc = run(
                from_category="Business:Bank Fees",
                to_category="Mojility:Bank Fees",
                data_dir=data_dir,
                write=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Mojility"
            assert groups[0].primary.subcategory == "Bank Fees"
            # Second transaction should remain unchanged
            assert groups[1].primary.category == "Business"
            assert groups[1].primary.subcategory == "Loan"

    def it_should_rename_category_without_subcategory(self):
        """Test renaming a category that has no subcategories."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Misc Expense",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Miscellaneous",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(
                from_category="Miscellaneous",
                to_category="Other",
                data_dir=data_dir,
                write=True,
            )
            assert rc == 0
            
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Other"
            assert groups[0].primary.subcategory is None

    def it_should_return_zero_when_no_matches(self):
        """Test that command returns 0 when no transactions match."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
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
            
            rc = run(
                from_category="NonExistent",
                to_category="Other",
                data_dir=data_dir,
                write=False,
            )
            assert rc == 0

    def it_should_work_across_multiple_accounts(self):
        """Test that renaming works across multiple ledger files."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            # Create two ledgers
            for account in ["ACCOUNT1", "ACCOUNT2"]:
                ledger_path = data_dir / f"{account}.csv"
                groups = [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id=f"{account}1111111111",
                            date="2025-01-01",
                            description="Business Expense",
                            amount=-100.0,
                            currency="CAD",
                            account_id=account,
                            category="Business",
                            subcategory="Supplies",
                        ),
                    ),
                ]
                _write_ledger(ledger_path, groups)
            
            rc = run(
                from_category="Business",
                to_category="Mojility",
                data_dir=data_dir,
                write=True,
            )
            assert rc == 0
            
            # Verify both accounts updated
            for account in ["ACCOUNT1", "ACCOUNT2"]:
                ledger_path = data_dir / f"{account}.csv"
                groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
                assert groups[0].primary.category == "Mojility"
                assert groups[0].primary.subcategory == "Supplies"

    def it_should_error_on_empty_from_category(self):
        """Test that empty --from category returns error."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            rc = run(
                from_category="",
                to_category="Other",
                data_dir=data_dir,
                write=False,
            )
            assert rc == 1

    def it_should_error_on_empty_to_category(self):
        """Test that empty --to category returns error."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            rc = run(
                from_category="Business",
                to_category="",
                data_dir=data_dir,
                write=False,
            )
            assert rc == 1
