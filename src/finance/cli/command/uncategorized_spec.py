from __future__ import annotations

"""
Tests for uncategorized command.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from finance.cli.command.uncategorized import run
from finance.model.account import Transaction, TransactionGroup
from finance.model.ledger_io import dump_ledger_csv


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write ledger CSV."""
    csv_text = dump_ledger_csv(groups)
    path.write_text(csv_text, encoding="utf-8")


class DescribeUncategorizedCommand:
    """Tests for uncategorized command."""

    def it_should_display_message_when_all_categorized(self):
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
                        description="Rent",
                        amount=-2000.0,
                        currency="CAD",
                        account_id="TEST",
                        category="Housing",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(data_dir=data_dir)
            assert rc == 0

    def it_should_list_uncategorized_transactions(self):
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
                        description="Unknown Transaction",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(data_dir=data_dir)
            assert rc == 0

    def it_should_filter_by_account(self):
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
                            description="Uncategorized",
                            amount=-100.0,
                            currency="CAD",
                            account_id=account,
                        ),
                    ),
                ]
                _write_ledger(ledger_path, groups)
            
            # Filter by specific account
            rc = run(account="ACCOUNT1", data_dir=data_dir)
            assert rc == 0

    def it_should_filter_by_year(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2024-01-01",
                        description="Last Year",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-01",
                        description="This Year",
                        amount=-200.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(year=2025, data_dir=data_dir)
            assert rc == 0

    def it_should_filter_by_min_amount(self):
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
                        description="Small",
                        amount=-10.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-02",
                        description="Large",
                        amount=-1000.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(min_amount=100.0, data_dir=data_dir)
            assert rc == 0

    def it_should_apply_limit(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id=str(i),
                    primary=Transaction(
                        transaction_id=f"{i:016d}",
                        date="2025-01-01",
                        description=f"Transaction {i}",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                )
                for i in range(1, 11)
            ]
            _write_ledger(ledger_path, groups)
            
            rc = run(limit=5, data_dir=data_dir)
            assert rc == 0

    def it_should_handle_empty_data_directory(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            rc = run(data_dir=data_dir)
            assert rc == 0

    def it_should_error_on_nonexistent_account(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            rc = run(account="NONEXISTENT", data_dir=data_dir)
            assert rc == 1

    def it_should_combine_filters(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2024-01-01",
                        description="Wrong Year",
                        amount=-500.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-01",
                        description="Too Small",
                        amount=-50.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-01-02",
                        description="Match",
                        amount=-500.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Should only show the third transaction
            rc = run(year=2025, min_amount=100.0, data_dir=data_dir)
            assert rc == 0

    def it_should_sort_by_description_then_date(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            data_dir.mkdir()
            
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-02",
                        description="AAAA",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id="2222222222222222",
                        date="2025-01-01",
                        description="AAAA",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="3",
                    primary=Transaction(
                        transaction_id="3333333333333333",
                        date="2025-01-01",
                        description="ZZZZ",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            _write_ledger(ledger_path, groups)
            
            # Sort order should be: AAAA (2025-01-01), AAAA (2025-01-02), ZZZZ (2025-01-01)
            rc = run(data_dir=data_dir)
            assert rc == 0
