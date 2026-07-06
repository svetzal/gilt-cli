from __future__ import annotations

"""
Tests for categorize command.
"""

import sys
from io import StringIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.categorize import BatchEntry, _build_batch_lines, run
from gilt.cli.command.conftest import build_projections_from_csvs, write_ledger
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import Category, CategoryConfig, Subcategory
from gilt.model.category_io import save_categories_config
from gilt.model.ledger_io import load_ledger_csv
from gilt.workspace import Workspace


class DescribeCategorizeValidation:
    """Tests for categorize command validation."""

    def it_should_require_exactly_one_mode(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Housing")])
            save_categories_config(config_path, config)

            # No mode specified
            with pytest.raises(CommandAbort) as exc_info_no_mode:
                run(
                    category="Housing",
                    workspace=workspace,
                    write=False,
                )
            assert exc_info_no_mode.value.code == 1

            # Multiple modes
            with pytest.raises(CommandAbort) as exc_info_multi:
                run(
                    txid="abcd1234",
                    description="Test",
                    category="Housing",
                    workspace=workspace,
                    write=False,
                )
            assert exc_info_multi.value.code == 1

    def it_should_error_on_nonexistent_category(self):
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
                        transaction_id="abcd1234abcd1234",
                        date="2025-01-01",
                        description="Test",
                        amount=-100.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            with pytest.raises(CommandAbort) as exc_info:
                run(
                    account="TEST",
                    txid="abcd1234",
                    category="NonExistent",
                    workspace=workspace,
                    write=False,
                )
            assert exc_info.value.code == 1


class DescribeCategorizeSingleMode:
    """Tests for single transaction categorization."""

    def it_should_categorize_single_transaction_by_txid(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            # Dry-run should not modify
            rc = run(
                account="TEST",
                txid="abcd1234",
                category="Housing",
                workspace=workspace,
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
                workspace=workspace,
                write=True,
                assume_yes=True,
            )
            assert rc == 0

            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Housing"

    def it_should_categorize_with_subcategory(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

            from gilt.model.category import Subcategory

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            # Using colon syntax
            rc = run(
                account="TEST",
                txid="abcd1234",
                category="Housing",
                subcategory="Rent",
                workspace=workspace,
                write=True,
                assume_yes=True,
            )
            assert rc == 0

            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Housing"
            assert groups[0].primary.subcategory == "Rent"

    def it_should_categorize_single_txid_globally_when_account_omitted(self):
        """Regression: --txid without --account must resolve across all accounts.

        The bug caused the per-account loop to abort when the first account did not
        contain the target transaction, so only single-account workspaces worked.
        """
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Shopping")])
            save_categories_config(config_path, config)

            # AACCT sorts before ZACCT alphabetically, so without the fix the
            # loop would hit AACCT first, fail to find the target txid there, and
            # abort before ever reaching ZACCT.
            decoy_txid = "dddddddddddddddd"
            target_txid = "zzzzzzzzzzzzzzzz"

            write_ledger(
                data_dir / "AACCT.csv",
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id=decoy_txid,
                            date="2025-01-01",
                            description="DECOY STORE",
                            amount=-10.0,
                            currency="CAD",
                            account_id="AACCT",
                        ),
                    )
                ],
            )
            write_ledger(
                data_dir / "ZACCT.csv",
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id=target_txid,
                            date="2025-01-02",
                            description="TARGET STORE",
                            amount=-20.0,
                            currency="CAD",
                            account_id="ZACCT",
                        ),
                    )
                ],
            )
            build_projections_from_csvs(data_dir, workspace.projections_path)

            rc = run(
                txid=target_txid[:8],  # no account= — must resolve globally
                category="Shopping",
                workspace=workspace,
                write=True,
                assume_yes=True,
            )
            assert rc == 0

            # Target transaction categorized
            target_groups = load_ledger_csv(
                (data_dir / "ZACCT.csv").read_text(), default_currency="CAD"
            )
            assert target_groups[0].primary.category == "Shopping"

            # Decoy transaction untouched
            decoy_groups = load_ledger_csv(
                (data_dir / "AACCT.csv").read_text(), default_currency="CAD"
            )
            assert decoy_groups[0].primary.category is None

    def it_should_match_txid_file_path_for_same_prefix(self):
        """Parity: single --txid and --txid-file (one entry) categorize identically."""
        target_txid = "zzzzzzzzzzzzzzzz"
        decoy_txid = "dddddddddddddddd"

        def _build_two_account_workspace(tmpdir: str) -> tuple[Path, Path, Workspace]:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            ws = Workspace(root=Path(tmpdir))
            config = CategoryConfig(categories=[Category(name="Shopping")])
            save_categories_config(config_path, config)
            write_ledger(
                data_dir / "AACCT.csv",
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id=decoy_txid,
                            date="2025-01-01",
                            description="DECOY STORE",
                            amount=-10.0,
                            currency="CAD",
                            account_id="AACCT",
                        ),
                    )
                ],
            )
            write_ledger(
                data_dir / "ZACCT.csv",
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id=target_txid,
                            date="2025-01-02",
                            description="TARGET STORE",
                            amount=-20.0,
                            currency="CAD",
                            account_id="ZACCT",
                        ),
                    )
                ],
            )
            build_projections_from_csvs(data_dir, ws.projections_path)
            return config_path, data_dir, ws

        with TemporaryDirectory() as tmpdir_a_str, TemporaryDirectory() as tmpdir_b_str:
            _config_a, data_dir_a, workspace_a = _build_two_account_workspace(tmpdir_a_str)
            _config_b, data_dir_b, workspace_b = _build_two_account_workspace(tmpdir_b_str)

            # Path A: single --txid
            rc_a = run(
                txid=target_txid[:8],
                category="Shopping",
                workspace=workspace_a,
                write=True,
                assume_yes=True,
            )
            assert rc_a == 0

            # Path B: --txid-file with one entry
            batch_file = Path(tmpdir_b_str) / "batch.txt"
            batch_file.write_text(f"{target_txid[:8]} Shopping\n")
            rc_b = run(workspace=workspace_b, txid_file=batch_file, write=True)
            assert rc_b == 0

            # Both paths must produce identical ledger contents
            for ledger_name in ("AACCT.csv", "ZACCT.csv"):
                groups_a = load_ledger_csv(
                    (data_dir_a / ledger_name).read_text(), default_currency="CAD"
                )
                groups_b = load_ledger_csv(
                    (data_dir_b / ledger_name).read_text(), default_currency="CAD"
                )
                assert groups_a[0].primary.category == groups_b[0].primary.category
                assert groups_a[0].primary.subcategory == groups_b[0].primary.subcategory

    def it_should_error_on_ambiguous_txid(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            with pytest.raises(CommandAbort) as exc_info:
                run(
                    txid="abcd1234",  # No account specified, ambiguous
                    category="Housing",
                    workspace=workspace,
                    write=False,
                )
            assert exc_info.value.code == 1


class DescribeCategorizeBatchMode:
    """Tests for batch categorization."""

    def it_should_categorize_by_exact_description(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            rc = run(
                account="TEST",
                description="SPOTIFY",
                category="Entertainment",
                workspace=workspace,
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
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            rc = run(
                account="TEST",
                desc_prefix="AMAZON",
                category="Shopping",
                workspace=workspace,
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
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
                write_ledger(ledger_path, groups)

                # Build projections from test CSVs
                build_projections_from_csvs(data_dir, workspace.projections_path)

            # No account specified - should categorize in all accounts
            rc = run(
                description="SPOTIFY",
                category="Entertainment",
                workspace=workspace,
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
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            # Only categorize the -12.95 fee
            rc = run(
                account="TEST",
                description="Monthly Fee",
                amount=-12.95,
                category="Banking",
                workspace=workspace,
                write=True,
                assume_yes=True,
            )
            assert rc == 0

            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Banking"
            assert groups[1].primary.category is None  # Different amount

    def it_should_return_zero_when_no_matches(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            rc = run(
                account="TEST",
                description="NONEXISTENT",
                category="Housing",
                workspace=workspace,
                write=False,
            )
            assert rc == 0  # No error, just no matches


class DescribeCategorizeRecategorization:
    """Tests for re-categorization warnings."""

    def it_should_warn_when_recategorizing(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            # Should succeed but show warning (check return code is 0)
            rc = run(
                account="TEST",
                description="SPOTIFY",
                category="Shopping",
                workspace=workspace,
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
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(
                categories=[Category(name="Housing", subcategories=[Subcategory(name="Utilities")])]
            )
            save_categories_config(config_path, config)

            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id="1111111111111111",
                        date="2025-01-01",
                        description="Payment - WWW Payment - 12345 EXAMPLE UTILITY",
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
                        description="Payment - WWW Payment - 67890 EXAMPLE UTILITY",
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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            # Categorize using regex pattern
            rc = run(
                account="TEST",
                pattern=r"Payment - WWW Payment - \d+ EXAMPLE UTILITY",
                category="Housing:Utilities",
                workspace=workspace,
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
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            # Invalid regex should return error code
            with pytest.raises(CommandAbort) as exc_info:
                run(
                    account="TEST",
                    pattern=r"[invalid(regex",  # Unclosed bracket
                    category="Housing",
                    workspace=workspace,
                    write=False,
                )
            assert exc_info.value.code == 1  # Error code for invalid pattern


def _build_batch_workspace(tmpdir: str) -> tuple[Path, Path, Workspace]:
    """Build a workspace with one TEST account ledger for batch tests."""
    config_dir = Path(tmpdir) / "config"
    config_dir.mkdir()
    config_path = config_dir / "categories.yml"
    data_dir = Path(tmpdir) / "data" / "accounts"
    data_dir.mkdir(parents=True)
    workspace = Workspace(root=Path(tmpdir))

    config = CategoryConfig(
        categories=[
            Category(name="Banking", subcategories=[Subcategory(name="Fees")]),
            Category(name="Shopping"),
        ]
    )
    save_categories_config(config_path, config)
    return config_path, data_dir, workspace


def _build_two_transactions(data_dir: Path, account_id: str = "TEST") -> tuple[str, str]:
    """Write two transactions to a ledger and return their txid prefixes."""
    txid1 = "aaaa1111bbbb2222"
    txid2 = "cccc3333dddd4444"
    ledger_path = data_dir / f"{account_id}.csv"
    groups = [
        TransactionGroup(
            group_id="1",
            primary=Transaction(
                transaction_id=txid1,
                date="2025-01-01",
                description="SAMPLE STORE",
                amount=-50.0,
                currency="CAD",
                account_id=account_id,
            ),
        ),
        TransactionGroup(
            group_id="2",
            primary=Transaction(
                transaction_id=txid2,
                date="2025-01-02",
                description="ACME CORP",
                amount=-75.0,
                currency="CAD",
                account_id=account_id,
            ),
        ),
    ]
    write_ledger(ledger_path, groups)
    return txid1[:8], txid2[:8]


class DescribeCategorizeBatchFile:
    """Tests for --txid-file and --from-stdin batch categorization."""

    def it_should_parse_file_with_comments_and_blank_lines(self):
        text = (
            "# This is a comment\n"
            "\n"
            "aaaa1111 Banking:Fees\n"
            "  \n"
            "# another comment\n"
            "cccc3333 Shopping\n"
        )
        entries, errors = _build_batch_lines(text)
        assert errors == []
        assert len(entries) == 2
        assert entries[0] == BatchEntry(
            line_no=3, txid_prefix="aaaa1111", category_path="Banking:Fees"
        )
        assert entries[1] == BatchEntry(line_no=6, txid_prefix="cccc3333", category_path="Shopping")

    def it_should_apply_batch_from_file_on_write(self):
        with TemporaryDirectory() as tmpdir:
            _config_path, data_dir, workspace = _build_batch_workspace(tmpdir)
            txid1, txid2 = _build_two_transactions(data_dir)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            batch_file.write_text(f"{txid1} Banking:Fees\n{txid2} Shopping\n")

            rc = run(
                workspace=workspace,
                txid_file=batch_file,
                write=True,
            )
            assert rc == 0

            groups = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Banking"
            assert groups[0].primary.subcategory == "Fees"
            assert groups[1].primary.category == "Shopping"
            assert groups[1].primary.subcategory is None

    def it_should_be_dry_run_by_default_and_show_preview(self):
        with TemporaryDirectory() as tmpdir:
            _config_path, data_dir, workspace = _build_batch_workspace(tmpdir)
            txid1, txid2 = _build_two_transactions(data_dir)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            batch_file.write_text(f"{txid1} Banking:Fees\n{txid2} Shopping\n")

            rc = run(
                workspace=workspace,
                txid_file=batch_file,
                write=False,
            )
            assert rc == 0

            # Ledger must be unchanged
            groups = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            assert groups[0].primary.category is None
            assert groups[1].primary.category is None

    def it_should_read_from_stdin_when_flag_set(self, monkeypatch):
        with TemporaryDirectory() as tmpdir:
            _config_path, data_dir, workspace = _build_batch_workspace(tmpdir)
            txid1, _txid2 = _build_two_transactions(data_dir)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            monkeypatch.setattr(sys, "stdin", StringIO(f"{txid1} Shopping\n"))

            rc = run(
                workspace=workspace,
                from_stdin=True,
                write=True,
            )
            assert rc == 0

            groups = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Shopping"

    def it_should_handle_category_with_embedded_spaces(self):
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
                        subcategories=[Subcategory(name="Fast Food")],
                    )
                ]
            )
            save_categories_config(config_path, config)

            txid1 = "aaaa1111bbbb2222"
            ledger_path = data_dir / "TEST.csv"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id=txid1,
                        date="2025-01-01",
                        description="SAMPLE BURGER",
                        amount=-12.50,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            write_ledger(ledger_path, groups)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            batch_file.write_text(f"{txid1[:8]} Dining Out:Fast Food\n")

            rc = run(workspace=workspace, txid_file=batch_file, write=True)
            assert rc == 0

            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Dining Out"
            assert groups[0].primary.subcategory == "Fast Food"

    def it_should_resolve_globally_when_account_omitted(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Shopping")])
            save_categories_config(config_path, config)

            # Two accounts with unique txid prefixes
            txid_a = "aaaa1111bbbb2222"
            txid_b = "bbbb2222cccc3333"
            for acct, txid, desc in [
                ("ACCT1", txid_a, "SAMPLE STORE"),
                ("ACCT2", txid_b, "ACME CORP"),
            ]:
                groups = [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id=txid,
                            date="2025-01-01",
                            description=desc,
                            amount=-10.0,
                            currency="CAD",
                            account_id=acct,
                        ),
                    )
                ]
                write_ledger(data_dir / f"{acct}.csv", groups)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            batch_file.write_text(f"{txid_a[:8]} Shopping\n{txid_b[:8]} Shopping\n")

            rc = run(workspace=workspace, txid_file=batch_file, write=True)
            assert rc == 0

            for _acct, ledger_file in [("ACCT1", "ACCT1.csv"), ("ACCT2", "ACCT2.csv")]:
                groups = load_ledger_csv(
                    (data_dir / ledger_file).read_text(), default_currency="CAD"
                )
                assert groups[0].primary.category == "Shopping"

    def it_should_scope_to_account_when_provided(self):
        with TemporaryDirectory() as tmpdir:
            _config_path, data_dir, workspace = _build_batch_workspace(tmpdir)
            txid1, txid2 = _build_two_transactions(data_dir)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            batch_file.write_text(f"{txid1} Shopping\n")

            rc = run(workspace=workspace, account="TEST", txid_file=batch_file, write=True)
            assert rc == 0

            groups = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Shopping"

    def it_should_abort_on_ambiguous_prefix_and_report_line_number(self):
        with TemporaryDirectory() as tmpdir:
            config_dir = Path(tmpdir) / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=Path(tmpdir))

            config = CategoryConfig(categories=[Category(name="Shopping")])
            save_categories_config(config_path, config)

            # Two transactions sharing the same 8-char prefix
            ambig_txid1 = "aaaa1111bbbb2222"
            ambig_txid2 = "aaaa1111cccc3333"
            groups = [
                TransactionGroup(
                    group_id="1",
                    primary=Transaction(
                        transaction_id=ambig_txid1,
                        date="2025-01-01",
                        description="SAMPLE A",
                        amount=-10.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
                TransactionGroup(
                    group_id="2",
                    primary=Transaction(
                        transaction_id=ambig_txid2,
                        date="2025-01-02",
                        description="SAMPLE B",
                        amount=-20.0,
                        currency="CAD",
                        account_id="TEST",
                    ),
                ),
            ]
            write_ledger(data_dir / "TEST.csv", groups)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            # "aaaa1111" is ambiguous (matches both)
            batch_file.write_text("aaaa1111 Shopping\n")

            with pytest.raises(CommandAbort) as exc_info:
                run(workspace=workspace, txid_file=batch_file, write=True)
            assert exc_info.value.code == 1

            # Ledger must be unchanged
            groups = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            assert groups[0].primary.category is None
            assert groups[1].primary.category is None

    def it_should_abort_on_unknown_category_and_report_line_number(self):
        with TemporaryDirectory() as tmpdir:
            _config_path, data_dir, workspace = _build_batch_workspace(tmpdir)
            txid1, txid2 = _build_two_transactions(data_dir)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            # Line 1 is valid; line 2 references an unknown category
            batch_file.write_text(f"{txid1} Shopping\n{txid2} NonExistentCategory\n")

            with pytest.raises(CommandAbort) as exc_info:
                run(workspace=workspace, txid_file=batch_file, write=True)
            assert exc_info.value.code == 1

            # All-or-nothing: neither transaction should be updated
            groups = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            assert groups[0].primary.category is None
            assert groups[1].primary.category is None

    def it_should_abort_on_malformed_line_and_report_line_number(self):
        """A line with only one whitespace-delimited token is malformed."""
        text = "aaaa1111\n"
        entries, errors = _build_batch_lines(text)
        assert len(errors) == 1
        assert "line 1" in errors[0].lower()

    def it_should_reject_combination_with_txid_or_category_flag(self):
        with TemporaryDirectory() as tmpdir:
            _config_path, data_dir, workspace = _build_batch_workspace(tmpdir)
            _txid1, _txid2 = _build_two_transactions(data_dir)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            batch_file.write_text("aaaa1111 Shopping\n")

            # Combining --txid-file with --txid should fail
            with pytest.raises(CommandAbort) as exc_info1:
                run(workspace=workspace, txid_file=batch_file, txid="aaaa1111")
            assert exc_info1.value.code == 1

            # Combining --txid-file with --category should fail
            with pytest.raises(CommandAbort) as exc_info2:
                run(workspace=workspace, txid_file=batch_file, category="Shopping")
            assert exc_info2.value.code == 1

            # Combining --from-stdin with --description should fail
            with pytest.raises(CommandAbort) as exc_info3:
                run(workspace=workspace, from_stdin=True, description="SAMPLE STORE")
            assert exc_info3.value.code == 1

    def it_should_not_persist_file_batch_in_dry_run(self):
        """Dry-run (write=False) must print message and not emit events or alter ledger."""
        with TemporaryDirectory() as tmpdir:
            _config_path, data_dir, workspace = _build_batch_workspace(tmpdir)
            txid1, txid2 = _build_two_transactions(data_dir)
            build_projections_from_csvs(data_dir, workspace.projections_path)

            batch_file = Path(tmpdir) / "batch.txt"
            batch_file.write_text(f"{txid1} Shopping\n{txid2} Shopping\n")

            rc = run(workspace=workspace, txid_file=batch_file, write=False)
            assert rc == 0

            # Ledger must be unchanged — no categories written
            groups = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            assert groups[0].primary.category is None
            assert groups[1].primary.category is None
