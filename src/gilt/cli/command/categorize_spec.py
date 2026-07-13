from __future__ import annotations

"""
Tests for categorize command.
"""

import sys
from io import StringIO
from pathlib import Path

import pytest

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.categorize import BatchEntry, _build_batch_lines, run
from gilt.model.category import Category, CategoryConfig, Subcategory
from gilt.model.ledger_io import load_ledger_csv
from gilt.testing import (
    build_projections_from_csvs,
    build_workspace_with_ledger,
    make_group,
    write_ledger,
)


class DescribeCategorizeValidation:
    """Tests for categorize command validation."""

    def it_should_require_exactly_one_mode(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path, config=CategoryConfig(categories=[Category(name="Housing")])
        )

        # No mode specified
        with pytest.raises(CommandAbort) as exc_info_no_mode:
            run(
                category="Housing",
                workspace=ws,
                write=False,
            )
        assert exc_info_no_mode.value.code == 1

        # Multiple modes
        with pytest.raises(CommandAbort) as exc_info_multi:
            run(
                txid="abcd1234",
                description="Test",
                category="Housing",
                workspace=ws,
                write=False,
            )
        assert exc_info_multi.value.code == 1

    def it_should_error_on_nonexistent_category(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="abcd1234abcd1234",
                    date="2025-01-01",
                    description="Test",
                    amount=-100.0,
                    account_id="TEST",
                )
            ],
            config=CategoryConfig(categories=[]),
            projections=True,
        )

        with pytest.raises(CommandAbort) as exc_info:
            run(
                account="TEST",
                txid="abcd1234",
                category="NonExistent",
                workspace=ws,
                write=False,
            )
        assert exc_info.value.code == 1


class DescribeCategorizeSingleMode:
    """Tests for single transaction categorization."""

    def it_should_categorize_single_transaction_by_txid(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="abcd1234abcd1234",
                    date="2025-01-01",
                    description="Rent",
                    amount=-2000.0,
                    account_id="TEST",
                )
            ],
            config=CategoryConfig(categories=[Category(name="Housing")]),
            projections=True,
        )
        ledger_path = ws.ledger_data_dir / "TEST.csv"

        # Dry-run should not modify
        rc = run(
            account="TEST",
            txid="abcd1234",
            category="Housing",
            workspace=ws,
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
            workspace=ws,
            write=True,
            assume_yes=True,
        )
        assert rc == 0

        groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
        assert groups[0].primary.category == "Housing"

    def it_should_categorize_with_subcategory(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="abcd1234abcd1234",
                    date="2025-01-01",
                    description="Rent",
                    amount=-2000.0,
                    account_id="TEST",
                )
            ],
            config=CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        subcategories=[Subcategory(name="Rent")],
                    )
                ]
            ),
            projections=True,
        )
        ledger_path = ws.ledger_data_dir / "TEST.csv"

        # Using colon syntax
        rc = run(
            account="TEST",
            txid="abcd1234",
            category="Housing",
            subcategory="Rent",
            workspace=ws,
            write=True,
            assume_yes=True,
        )
        assert rc == 0

        groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
        assert groups[0].primary.category == "Housing"
        assert groups[0].primary.subcategory == "Rent"

    def it_should_categorize_single_txid_globally_when_account_omitted(self, tmp_path):
        """Regression: --txid without --account must resolve across all accounts.

        The bug caused the per-account loop to abort when the first account did not
        contain the target transaction, so only single-account workspaces worked.
        """
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(categories=[Category(name="Shopping")]),
        )

        # AACCT sorts before ZACCT alphabetically, so without the fix the
        # loop would hit AACCT first, fail to find the target txid there, and
        # abort before ever reaching ZACCT.
        decoy_txid = "dddddddddddddddd"
        target_txid = "zzzzzzzzzzzzzzzz"

        write_ledger(
            ws.ledger_data_dir / "AACCT.csv",
            [
                make_group(
                    transaction_id=decoy_txid,
                    date="2025-01-01",
                    description="DECOY STORE",
                    amount=-10.0,
                    account_id="AACCT",
                )
            ],
        )
        write_ledger(
            ws.ledger_data_dir / "ZACCT.csv",
            [
                make_group(
                    transaction_id=target_txid,
                    date="2025-01-02",
                    description="TARGET STORE",
                    amount=-20.0,
                    account_id="ZACCT",
                )
            ],
        )
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        rc = run(
            txid=target_txid[:8],  # no account= — must resolve globally
            category="Shopping",
            workspace=ws,
            write=True,
            assume_yes=True,
        )
        assert rc == 0

        # Target transaction categorized
        target_groups = load_ledger_csv(
            (ws.ledger_data_dir / "ZACCT.csv").read_text(), default_currency="CAD"
        )
        assert target_groups[0].primary.category == "Shopping"

        # Decoy transaction untouched
        decoy_groups = load_ledger_csv(
            (ws.ledger_data_dir / "AACCT.csv").read_text(), default_currency="CAD"
        )
        assert decoy_groups[0].primary.category is None

    def it_should_match_txid_file_path_for_same_prefix(self, tmp_path, tmp_path_factory):
        """Parity: single --txid and --txid-file (one entry) categorize identically."""
        target_txid = "zzzzzzzzzzzzzzzz"
        decoy_txid = "dddddddddddddddd"

        def _build_two_account_workspace(base_path: Path):
            ws = build_workspace_with_ledger(
                base_path,
                config=CategoryConfig(categories=[Category(name="Shopping")]),
            )
            write_ledger(
                ws.ledger_data_dir / "AACCT.csv",
                [
                    make_group(
                        transaction_id=decoy_txid,
                        date="2025-01-01",
                        description="DECOY STORE",
                        amount=-10.0,
                        account_id="AACCT",
                    )
                ],
            )
            write_ledger(
                ws.ledger_data_dir / "ZACCT.csv",
                [
                    make_group(
                        transaction_id=target_txid,
                        date="2025-01-02",
                        description="TARGET STORE",
                        amount=-20.0,
                        account_id="ZACCT",
                    )
                ],
            )
            build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)
            return ws

        path_a = tmp_path_factory.mktemp("ws_a")
        path_b = tmp_path_factory.mktemp("ws_b")
        workspace_a = _build_two_account_workspace(path_a)
        workspace_b = _build_two_account_workspace(path_b)

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
        batch_file = path_b / "batch.txt"
        batch_file.write_text(f"{target_txid[:8]} Shopping\n")
        rc_b = run(workspace=workspace_b, txid_file=batch_file, write=True)
        assert rc_b == 0

        # Both paths must produce identical ledger contents
        for ledger_name in ("AACCT.csv", "ZACCT.csv"):
            groups_a = load_ledger_csv(
                (workspace_a.ledger_data_dir / ledger_name).read_text(), default_currency="CAD"
            )
            groups_b = load_ledger_csv(
                (workspace_b.ledger_data_dir / ledger_name).read_text(), default_currency="CAD"
            )
            assert groups_a[0].primary.category == groups_b[0].primary.category
            assert groups_a[0].primary.subcategory == groups_b[0].primary.subcategory

    def it_should_error_on_ambiguous_txid(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="abcd1234abcd1234",
                    date="2025-01-01",
                    description="Rent 1",
                    amount=-2000.0,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id="abcd1234eeeeeeee",
                    date="2025-01-02",
                    description="Rent 2",
                    amount=-2000.0,
                    account_id="TEST",
                ),
            ],
            config=CategoryConfig(categories=[Category(name="Housing")]),
            projections=True,
        )

        with pytest.raises(CommandAbort) as exc_info:
            run(
                txid="abcd1234",  # No account specified, ambiguous
                category="Housing",
                workspace=ws,
                write=False,
            )
        assert exc_info.value.code == 1


class DescribeCategorizeBatchMode:
    """Tests for batch categorization."""

    def it_should_categorize_by_exact_description(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="SPOTIFY",
                    amount=-9.99,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id="2222222222222222",
                    date="2025-02-01",
                    description="SPOTIFY",
                    amount=-9.99,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id="3333333333333333",
                    date="2025-03-01",
                    description="NETFLIX",
                    amount=-15.99,
                    account_id="TEST",
                ),
            ],
            config=CategoryConfig(categories=[Category(name="Entertainment")]),
            projections=True,
        )
        ledger_path = ws.ledger_data_dir / "TEST.csv"

        rc = run(
            account="TEST",
            description="SPOTIFY",
            category="Entertainment",
            workspace=ws,
            write=True,
            assume_yes=True,
        )
        assert rc == 0

        groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
        assert groups[0].primary.category == "Entertainment"
        assert groups[1].primary.category == "Entertainment"
        assert groups[2].primary.category is None  # Different description

    def it_should_categorize_by_description_prefix(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="AMAZON.COM ORDER 123",
                    amount=-50.0,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id="2222222222222222",
                    date="2025-02-01",
                    description="AMAZON.CA ORDER 456",
                    amount=-75.0,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id="3333333333333333",
                    date="2025-03-01",
                    description="WALMART",
                    amount=-25.0,
                    account_id="TEST",
                ),
            ],
            config=CategoryConfig(categories=[Category(name="Shopping")]),
            projections=True,
        )
        ledger_path = ws.ledger_data_dir / "TEST.csv"

        rc = run(
            account="TEST",
            desc_prefix="AMAZON",
            category="Shopping",
            workspace=ws,
            write=True,
            assume_yes=True,
        )
        assert rc == 0

        groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
        assert groups[0].primary.category == "Shopping"
        assert groups[1].primary.category == "Shopping"
        assert groups[2].primary.category is None  # Different prefix

    def it_should_categorize_across_multiple_accounts(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(categories=[Category(name="Entertainment")]),
        )

        # Create two ledgers
        for account in ["ACCOUNT1", "ACCOUNT2"]:
            write_ledger(
                ws.ledger_data_dir / f"{account}.csv",
                [
                    make_group(
                        transaction_id=f"{account}1111111111",
                        date="2025-01-01",
                        description="SPOTIFY",
                        amount=-9.99,
                        account_id=account,
                    )
                ],
            )

        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        # No account specified - should categorize in all accounts
        rc = run(
            description="SPOTIFY",
            category="Entertainment",
            workspace=ws,
            write=True,
            assume_yes=True,
        )
        assert rc == 0

        # Verify both accounts updated
        for account in ["ACCOUNT1", "ACCOUNT2"]:
            ledger_path = ws.ledger_data_dir / f"{account}.csv"
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Entertainment"

    def it_should_filter_by_amount_in_batch_mode(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Monthly Fee",
                    amount=-12.95,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id="2222222222222222",
                    date="2025-02-01",
                    description="Monthly Fee",
                    amount=-15.00,
                    account_id="TEST",
                ),
            ],
            config=CategoryConfig(categories=[Category(name="Banking")]),
            projections=True,
        )
        ledger_path = ws.ledger_data_dir / "TEST.csv"

        # Only categorize the -12.95 fee
        rc = run(
            account="TEST",
            description="Monthly Fee",
            amount=-12.95,
            category="Banking",
            workspace=ws,
            write=True,
            assume_yes=True,
        )
        assert rc == 0

        groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
        assert groups[0].primary.category == "Banking"
        assert groups[1].primary.category is None  # Different amount

    def it_should_return_zero_when_no_matches(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="SPOTIFY",
                    amount=-9.99,
                    account_id="TEST",
                )
            ],
            config=CategoryConfig(categories=[Category(name="Housing")]),
            projections=True,
        )

        rc = run(
            account="TEST",
            description="NONEXISTENT",
            category="Housing",
            workspace=ws,
            write=False,
        )
        assert rc == 0  # No error, just no matches


class DescribeCategorizeRecategorization:
    """Tests for re-categorization warnings."""

    def it_should_warn_when_recategorizing(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="SPOTIFY",
                    amount=-9.99,
                    account_id="TEST",
                    category="Entertainment",  # Already categorized
                )
            ],
            config=CategoryConfig(
                categories=[
                    Category(name="Entertainment"),
                    Category(name="Shopping"),
                ]
            ),
            projections=True,
        )
        ledger_path = ws.ledger_data_dir / "TEST.csv"

        # Should succeed but show warning (check return code is 0)
        rc = run(
            account="TEST",
            description="SPOTIFY",
            category="Shopping",
            workspace=ws,
            write=True,
            assume_yes=True,
        )
        assert rc == 0

        groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
        assert groups[0].primary.category == "Shopping"  # Updated


class DescribeCategorizePatternMode:
    """Tests for pattern matching mode."""

    def it_should_categorize_by_regex_pattern(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Payment - WWW Payment - 12345 EXAMPLE UTILITY",
                    amount=-150.0,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id="2222222222222222",
                    date="2025-02-01",
                    description="Payment - WWW Payment - 67890 EXAMPLE UTILITY",
                    amount=-145.0,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id="3333333333333333",
                    date="2025-03-01",
                    description="Payment - DIFFERENT VENDOR",
                    amount=-50.0,
                    account_id="TEST",
                ),
            ],
            config=CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        subcategories=[Subcategory(name="Utilities")],
                    )
                ]
            ),
            projections=True,
        )
        ledger_path = ws.ledger_data_dir / "TEST.csv"

        # Categorize using regex pattern
        rc = run(
            account="TEST",
            pattern=r"Payment - WWW Payment - \d+ EXAMPLE UTILITY",
            category="Housing:Utilities",
            workspace=ws,
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

    def it_should_error_on_invalid_regex_pattern(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="1111111111111111",
                    date="2025-01-01",
                    description="Test",
                    amount=-10.0,
                    account_id="TEST",
                )
            ],
            config=CategoryConfig(categories=[Category(name="Housing")]),
            projections=True,
        )

        # Invalid regex should return error code
        with pytest.raises(CommandAbort) as exc_info:
            run(
                account="TEST",
                pattern=r"[invalid(regex",  # Unclosed bracket
                category="Housing",
                workspace=ws,
                write=False,
            )
        assert exc_info.value.code == 1  # Error code for invalid pattern


def _build_batch_workspace(tmp_path: Path):
    """Build a workspace with Banking and Shopping categories for batch tests."""
    from gilt.model.category import Subcategory

    ws = build_workspace_with_ledger(
        tmp_path,
        config=CategoryConfig(
            categories=[
                Category(name="Banking", subcategories=[Subcategory(name="Fees")]),
                Category(name="Shopping"),
            ]
        ),
    )
    return ws


def _build_two_transactions(ws, account_id: str = "TEST") -> tuple[str, str]:
    """Write two transactions to a ledger and return their txid prefixes."""
    txid1 = "aaaa1111bbbb2222"
    txid2 = "cccc3333dddd4444"
    write_ledger(
        ws.ledger_data_dir / f"{account_id}.csv",
        [
            make_group(
                transaction_id=txid1,
                date="2025-01-01",
                description="SAMPLE STORE",
                amount=-50.0,
                account_id=account_id,
            ),
            make_group(
                transaction_id=txid2,
                date="2025-01-02",
                description="ACME CORP",
                amount=-75.0,
                account_id=account_id,
            ),
        ],
    )
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

    def it_should_apply_batch_from_file_on_write(self, tmp_path):
        ws = _build_batch_workspace(tmp_path)
        txid1, txid2 = _build_two_transactions(ws)
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        batch_file.write_text(f"{txid1} Banking:Fees\n{txid2} Shopping\n")

        rc = run(
            workspace=ws,
            txid_file=batch_file,
            write=True,
        )
        assert rc == 0

        groups = load_ledger_csv(
            (ws.ledger_data_dir / "TEST.csv").read_text(), default_currency="CAD"
        )
        assert groups[0].primary.category == "Banking"
        assert groups[0].primary.subcategory == "Fees"
        assert groups[1].primary.category == "Shopping"
        assert groups[1].primary.subcategory is None

    def it_should_be_dry_run_by_default_and_show_preview(self, tmp_path):
        ws = _build_batch_workspace(tmp_path)
        txid1, txid2 = _build_two_transactions(ws)
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        batch_file.write_text(f"{txid1} Banking:Fees\n{txid2} Shopping\n")

        rc = run(
            workspace=ws,
            txid_file=batch_file,
            write=False,
        )
        assert rc == 0

        # Ledger must be unchanged
        groups = load_ledger_csv(
            (ws.ledger_data_dir / "TEST.csv").read_text(), default_currency="CAD"
        )
        assert groups[0].primary.category is None
        assert groups[1].primary.category is None

    def it_should_read_from_stdin_when_flag_set(self, tmp_path, monkeypatch):
        ws = _build_batch_workspace(tmp_path)
        txid1, _txid2 = _build_two_transactions(ws)
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        monkeypatch.setattr(sys, "stdin", StringIO(f"{txid1} Shopping\n"))

        rc = run(
            workspace=ws,
            from_stdin=True,
            write=True,
        )
        assert rc == 0

        groups = load_ledger_csv(
            (ws.ledger_data_dir / "TEST.csv").read_text(), default_currency="CAD"
        )
        assert groups[0].primary.category == "Shopping"

    def it_should_handle_category_with_embedded_spaces(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(
                categories=[
                    Category(
                        name="Dining Out",
                        subcategories=[Subcategory(name="Fast Food")],
                    )
                ]
            ),
        )
        txid1 = "aaaa1111bbbb2222"
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    transaction_id=txid1,
                    date="2025-01-01",
                    description="SAMPLE BURGER",
                    amount=-12.50,
                    account_id="TEST",
                )
            ],
        )
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        batch_file.write_text(f"{txid1[:8]} Dining Out:Fast Food\n")

        rc = run(workspace=ws, txid_file=batch_file, write=True)
        assert rc == 0

        groups = load_ledger_csv(
            (ws.ledger_data_dir / "TEST.csv").read_text(), default_currency="CAD"
        )
        assert groups[0].primary.category == "Dining Out"
        assert groups[0].primary.subcategory == "Fast Food"

    def it_should_resolve_globally_when_account_omitted(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(categories=[Category(name="Shopping")]),
        )

        # Two accounts with unique txid prefixes
        txid_a = "aaaa1111bbbb2222"
        txid_b = "bbbb2222cccc3333"
        for acct, txid, desc in [
            ("ACCT1", txid_a, "SAMPLE STORE"),
            ("ACCT2", txid_b, "ACME CORP"),
        ]:
            write_ledger(
                ws.ledger_data_dir / f"{acct}.csv",
                [
                    make_group(
                        transaction_id=txid,
                        date="2025-01-01",
                        description=desc,
                        amount=-10.0,
                        account_id=acct,
                    )
                ],
            )
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        batch_file.write_text(f"{txid_a[:8]} Shopping\n{txid_b[:8]} Shopping\n")

        rc = run(workspace=ws, txid_file=batch_file, write=True)
        assert rc == 0

        for _acct, ledger_file in [("ACCT1", "ACCT1.csv"), ("ACCT2", "ACCT2.csv")]:
            groups = load_ledger_csv(
                (ws.ledger_data_dir / ledger_file).read_text(), default_currency="CAD"
            )
            assert groups[0].primary.category == "Shopping"

    def it_should_scope_to_account_when_provided(self, tmp_path):
        ws = _build_batch_workspace(tmp_path)
        txid1, _txid2 = _build_two_transactions(ws)
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        batch_file.write_text(f"{txid1} Shopping\n")

        rc = run(workspace=ws, account="TEST", txid_file=batch_file, write=True)
        assert rc == 0

        groups = load_ledger_csv(
            (ws.ledger_data_dir / "TEST.csv").read_text(), default_currency="CAD"
        )
        assert groups[0].primary.category == "Shopping"

    def it_should_abort_on_ambiguous_prefix_and_report_line_number(self, tmp_path):
        ws = build_workspace_with_ledger(
            tmp_path,
            config=CategoryConfig(categories=[Category(name="Shopping")]),
        )

        # Two transactions sharing the same 8-char prefix
        ambig_txid1 = "aaaa1111bbbb2222"
        ambig_txid2 = "aaaa1111cccc3333"
        write_ledger(
            ws.ledger_data_dir / "TEST.csv",
            [
                make_group(
                    transaction_id=ambig_txid1,
                    date="2025-01-01",
                    description="SAMPLE A",
                    amount=-10.0,
                    account_id="TEST",
                ),
                make_group(
                    transaction_id=ambig_txid2,
                    date="2025-01-02",
                    description="SAMPLE B",
                    amount=-20.0,
                    account_id="TEST",
                ),
            ],
        )
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        # "aaaa1111" is ambiguous (matches both)
        batch_file.write_text("aaaa1111 Shopping\n")

        with pytest.raises(CommandAbort) as exc_info:
            run(workspace=ws, txid_file=batch_file, write=True)
        assert exc_info.value.code == 1

        # Ledger must be unchanged
        groups = load_ledger_csv(
            (ws.ledger_data_dir / "TEST.csv").read_text(), default_currency="CAD"
        )
        assert groups[0].primary.category is None
        assert groups[1].primary.category is None

    def it_should_abort_on_unknown_category_and_report_line_number(self, tmp_path):
        ws = _build_batch_workspace(tmp_path)
        txid1, txid2 = _build_two_transactions(ws)
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        # Line 1 is valid; line 2 references an unknown category
        batch_file.write_text(f"{txid1} Shopping\n{txid2} NonExistentCategory\n")

        with pytest.raises(CommandAbort) as exc_info:
            run(workspace=ws, txid_file=batch_file, write=True)
        assert exc_info.value.code == 1

        # All-or-nothing: neither transaction should be updated
        groups = load_ledger_csv(
            (ws.ledger_data_dir / "TEST.csv").read_text(), default_currency="CAD"
        )
        assert groups[0].primary.category is None
        assert groups[1].primary.category is None

    def it_should_abort_on_malformed_line_and_report_line_number(self):
        """A line with only one whitespace-delimited token is malformed."""
        text = "aaaa1111\n"
        entries, errors = _build_batch_lines(text)
        assert len(errors) == 1
        assert "line 1" in errors[0].lower()

    def it_should_reject_combination_with_txid_or_category_flag(self, tmp_path):
        ws = _build_batch_workspace(tmp_path)
        _txid1, _txid2 = _build_two_transactions(ws)
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        batch_file.write_text("aaaa1111 Shopping\n")

        # Combining --txid-file with --txid should fail
        with pytest.raises(CommandAbort) as exc_info1:
            run(workspace=ws, txid_file=batch_file, txid="aaaa1111")
        assert exc_info1.value.code == 1

        # Combining --txid-file with --category should fail
        with pytest.raises(CommandAbort) as exc_info2:
            run(workspace=ws, txid_file=batch_file, category="Shopping")
        assert exc_info2.value.code == 1

        # Combining --from-stdin with --description should fail
        with pytest.raises(CommandAbort) as exc_info3:
            run(workspace=ws, from_stdin=True, description="SAMPLE STORE")
        assert exc_info3.value.code == 1

    def it_should_not_persist_file_batch_in_dry_run(self, tmp_path):
        """Dry-run (write=False) must print message and not emit events or alter ledger."""
        ws = _build_batch_workspace(tmp_path)
        txid1, txid2 = _build_two_transactions(ws)
        build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)

        batch_file = tmp_path / "batch.txt"
        batch_file.write_text(f"{txid1} Shopping\n{txid2} Shopping\n")

        rc = run(workspace=ws, txid_file=batch_file, write=False)
        assert rc == 0

        # Ledger must be unchanged — no categories written
        groups = load_ledger_csv(
            (ws.ledger_data_dir / "TEST.csv").read_text(), default_currency="CAD"
        )
        assert groups[0].primary.category is None
        assert groups[1].primary.category is None
