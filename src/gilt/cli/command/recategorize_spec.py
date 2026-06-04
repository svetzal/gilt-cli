from __future__ import annotations

"""
Tests for recategorize command.
"""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from typer.testing import CliRunner

from gilt.cli.command.conftest import build_projections_from_csvs, write_ledger
from gilt.cli.command.recategorize import build_date_selection, run
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.ledger_io import load_ledger_csv
from gilt.workspace import Workspace

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_txn(
    txn_id: str,
    description: str,
    amount: float,
    txn_date: str = "2025-01-15",
    account_id: str = "TEST",
    category: str | None = None,
    subcategory: str | None = None,
) -> TransactionGroup:
    return TransactionGroup(
        group_id=txn_id,
        primary=Transaction(
            transaction_id=txn_id,
            date=txn_date,
            description=description,
            amount=amount,
            currency="CAD",
            account_id=account_id,
            category=category,
            subcategory=subcategory,
        ),
    )


def _setup_workspace(tmpdir: str, groups_by_account: dict[str, list[TransactionGroup]]):
    """Write ledgers and build projections. Returns workspace."""
    root = Path(tmpdir)
    data_dir = root / "data" / "accounts"
    data_dir.mkdir(parents=True)
    workspace = Workspace(root=root)
    for account_id, groups in groups_by_account.items():
        ledger_path = data_dir / f"{account_id}.csv"
        write_ledger(ledger_path, groups)
    build_projections_from_csvs(data_dir, workspace.projections_path)
    return workspace, data_dir


# ---------------------------------------------------------------------------
# build_date_selection helper tests
# ---------------------------------------------------------------------------


class DescribeBuildDateSelection:
    """Tests for the build_date_selection pure helper."""

    def it_should_return_all_none_when_no_args_given(self):
        result = build_date_selection(None, None, None)
        assert result == (None, None, None)

    def it_should_parse_valid_date_from(self):
        result = build_date_selection("2025-01-15", None, None)
        assert isinstance(result, tuple)
        date_from, date_to, fy_range = result
        assert date_from == date(2025, 1, 15)
        assert date_to is None
        assert fy_range is None

    def it_should_parse_valid_date_to(self):
        result = build_date_selection(None, "2025-12-31", None)
        assert isinstance(result, tuple)
        date_from, date_to, fy_range = result
        assert date_from is None
        assert date_to == date(2025, 12, 31)

    def it_should_parse_valid_fy(self):
        result = build_date_selection(None, None, "FY25")
        assert isinstance(result, tuple)
        date_from, date_to, fy_range = result
        assert date_from is None
        assert date_to is None
        assert fy_range == (date(2024, 11, 1), date(2025, 10, 31))

    def it_should_return_error_string_for_invalid_date_from(self):
        result = build_date_selection("not-a-date", None, None)
        assert isinstance(result, str)
        assert "date-from" in result

    def it_should_return_error_string_for_invalid_date_to(self):
        result = build_date_selection(None, "99-99-99", None)
        assert isinstance(result, str)
        assert "date-to" in result

    def it_should_return_error_string_for_invalid_fy(self):
        result = build_date_selection(None, None, "INVALID")
        assert isinstance(result, str)

    def it_should_return_error_when_fy_and_date_from_both_set(self):
        result = build_date_selection("2025-01-01", None, "FY25")
        assert isinstance(result, str)
        assert "--fy" in result

    def it_should_return_error_when_fy_and_date_to_both_set(self):
        result = build_date_selection(None, "2025-12-31", "FY25")
        assert isinstance(result, str)
        assert "--fy" in result

    def it_should_parse_both_date_from_and_date_to(self):
        result = build_date_selection("2025-03-01", "2025-09-30", None)
        assert isinstance(result, tuple)
        date_from, date_to, fy_range = result
        assert date_from == date(2025, 3, 1)
        assert date_to == date(2025, 9, 30)
        assert fy_range is None


# ---------------------------------------------------------------------------
# Original rename-mode tests (unchanged)
# ---------------------------------------------------------------------------


class DescribeRecategorizeCommand:
    """Tests for recategorize command."""

    def it_should_rename_category_preserving_subcategories(self):
        """Test that renaming only the parent category preserves existing subcategories."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            # Dry-run should not modify
            rc = run(
                from_category="Business",
                to_category="Work",
                workspace=workspace,
                write=False,
            )
            assert rc == 0

            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Business"
            assert groups[0].primary.subcategory == "Bank Fees"

            # Write should rename category but preserve subcategories
            rc = run(
                from_category="Business",
                to_category="Work",
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Work"
            assert groups[0].primary.subcategory == "Bank Fees"
            assert groups[1].primary.category == "Work"
            assert groups[1].primary.subcategory == "Loan"
            assert groups[2].primary.category == "Work"
            assert groups[2].primary.subcategory == "Subscriptions"

    def it_should_rename_specific_subcategory(self):
        """Test that specifying both category and subcategory renames only that subcategory."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            # Rename only Business:Bank Fees to Work:Bank Fees
            rc = run(
                from_category="Business:Bank Fees",
                to_category="Work:Bank Fees",
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Work"
            assert groups[0].primary.subcategory == "Bank Fees"
            # Second transaction should remain unchanged
            assert groups[1].primary.category == "Business"
            assert groups[1].primary.subcategory == "Loan"

    def it_should_rename_category_without_subcategory(self):
        """Test renaming a category that has no subcategories."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            rc = run(
                from_category="Miscellaneous",
                to_category="Other",
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Other"
            assert groups[0].primary.subcategory is None

    def it_should_return_zero_when_no_matches(self):
        """Test that command returns 0 when no transactions match."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
            write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            rc = run(
                from_category="NonExistent",
                to_category="Other",
                workspace=workspace,
                write=False,
            )
            assert rc == 0

    def it_should_work_across_multiple_accounts(self):
        """Test that renaming works across multiple ledger files."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

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
                write_ledger(ledger_path, groups)

            # Build projections from test CSVs
            build_projections_from_csvs(data_dir, workspace.projections_path)

            rc = run(
                from_category="Business",
                to_category="Work",
                workspace=workspace,
                write=True,
            )
            assert rc == 0

            # Verify both accounts updated
            for account in ["ACCOUNT1", "ACCOUNT2"]:
                ledger_path = data_dir / f"{account}.csv"
                groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
                assert groups[0].primary.category == "Work"
                assert groups[0].primary.subcategory == "Supplies"

    def it_should_error_on_empty_from_category(self):
        """Test that empty --from category returns error."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

            rc = run(
                from_category="",
                to_category="Other",
                workspace=workspace,
                write=False,
            )
            assert rc == 1

    def it_should_error_on_empty_to_category(self):
        """Test that empty --to category returns error."""
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data" / "accounts"
            data_dir.mkdir(parents=True)

            workspace = Workspace(root=Path(tmpdir))

            rc = run(
                from_category="Business",
                to_category="",
                workspace=workspace,
                write=False,
            )
            assert rc == 1


# ---------------------------------------------------------------------------
# Selection mode — individual filter tests
# ---------------------------------------------------------------------------


class DescribeSelectionModeFilters:
    """Selection mode tests: each filter criterion in isolation."""

    def it_should_select_by_desc_prefix(self):
        """Transactions whose description starts with the prefix are selected; others unchanged."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    _make_txn(
                        "aaaa000000000001",
                        "ACME CORP subscription",
                        -18.30,
                        category="Entertainment",
                    ),
                    _make_txn(
                        "aaaa000000000002", "SAMPLE STORE groceries", -42.00, category="Groceries"
                    ),
                ]
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Work:Subscriptions",
                workspace=workspace,
                desc_prefix="ACME",
                write=True,
            )
            assert rc == 0

            ledger = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            by_id = {g.primary.transaction_id: g for g in ledger}
            assert by_id["aaaa000000000001"].primary.category == "Work"
            assert by_id["aaaa000000000001"].primary.subcategory == "Subscriptions"
            # Non-matching transaction must be untouched
            assert by_id["aaaa000000000002"].primary.category == "Groceries"

    def it_should_select_by_pattern(self):
        """Transactions matching the regex pattern are selected; others unchanged."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    _make_txn(
                        "bbbb000000000001",
                        "EXAMPLE UTILITY electric bill",
                        -120.00,
                        category="Housing",
                    ),
                    _make_txn(
                        "bbbb000000000002", "ACME CORP purchase", -55.00, category="Shopping"
                    ),
                ]
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Housing:Utilities",
                workspace=workspace,
                pattern=r"EXAMPLE.*UTILITY",
                write=True,
            )
            assert rc == 0

            ledger = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            by_id = {g.primary.transaction_id: g for g in ledger}
            assert by_id["bbbb000000000001"].primary.category == "Housing"
            assert by_id["bbbb000000000001"].primary.subcategory == "Utilities"
            # Non-matching transaction must be untouched
            assert by_id["bbbb000000000002"].primary.category == "Shopping"

    def it_should_select_by_amount_eq(self):
        """Only the exact signed amount matches: -18.30 debit is selected, +18.30 credit is not."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    _make_txn("cccc000000000001", "ACME CORP", -18.30, category="Entertainment"),
                    _make_txn("cccc000000000002", "REFUND ACME", 18.30, category="Income"),
                    _make_txn("cccc000000000003", "ACME CORP", -99.00, category="Entertainment"),
                ]
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Work:Subscriptions",
                workspace=workspace,
                amount_eq=-18.30,
                write=True,
            )
            assert rc == 0

            ledger = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            by_id = {g.primary.transaction_id: g for g in ledger}
            # Only the -18.30 debit should be recategorized
            assert by_id["cccc000000000001"].primary.category == "Work"
            assert by_id["cccc000000000001"].primary.subcategory == "Subscriptions"
            # The +18.30 credit must NOT be touched (strict signed match)
            assert by_id["cccc000000000002"].primary.category == "Income"
            # The -99.00 debit must NOT be touched
            assert by_id["cccc000000000003"].primary.category == "Entertainment"

    def it_should_select_by_amount_min_and_max(self):
        """Transactions with amount in [min, max] are selected; outside that range are not."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    _make_txn("dddd000000000001", "SAMPLE STORE", -10.00, category="Shopping"),
                    _make_txn("dddd000000000002", "SAMPLE STORE", -50.00, category="Shopping"),
                    _make_txn("dddd000000000003", "SAMPLE STORE", -200.00, category="Shopping"),
                ]
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Groceries",
                workspace=workspace,
                amount_min=-100.00,
                amount_max=-10.00,
                write=True,
            )
            assert rc == 0

            ledger = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            by_id = {g.primary.transaction_id: g for g in ledger}
            # -10.00 and -50.00 are within [-100, -10]; -200.00 is outside
            assert by_id["dddd000000000001"].primary.category == "Groceries"
            assert by_id["dddd000000000002"].primary.category == "Groceries"
            assert by_id["dddd000000000003"].primary.category == "Shopping"

    def it_should_select_by_account(self):
        """Only transactions in the specified account are selected; other accounts unchanged."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "MYBANK_CHQ": [
                    _make_txn(
                        "eeee000000000001",
                        "ACME CORP",
                        -18.30,
                        account_id="MYBANK_CHQ",
                        category="Entertainment",
                    ),
                ],
                "MYBANK_CC": [
                    _make_txn(
                        "eeee000000000002",
                        "ACME CORP",
                        -18.30,
                        account_id="MYBANK_CC",
                        category="Entertainment",
                    ),
                ],
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Work:Subscriptions",
                workspace=workspace,
                account="MYBANK_CC",
                write=True,
            )
            assert rc == 0

            chq_ledger = load_ledger_csv(
                (data_dir / "MYBANK_CHQ.csv").read_text(), default_currency="CAD"
            )
            cc_ledger = load_ledger_csv(
                (data_dir / "MYBANK_CC.csv").read_text(), default_currency="CAD"
            )
            # MYBANK_CC transaction should be recategorized
            assert cc_ledger[0].primary.category == "Work"
            assert cc_ledger[0].primary.subcategory == "Subscriptions"
            # MYBANK_CHQ transaction must be untouched
            assert chq_ledger[0].primary.category == "Entertainment"

    def it_should_select_by_date_from_and_date_to(self):
        """Only transactions within the date window are selected; outside dates are unchanged."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    _make_txn(
                        "ffff000000000001",
                        "ACME CORP",
                        -18.30,
                        txn_date="2025-01-01",
                        category="Shopping",
                    ),
                    _make_txn(
                        "ffff000000000002",
                        "ACME CORP",
                        -18.30,
                        txn_date="2025-06-15",
                        category="Shopping",
                    ),
                    _make_txn(
                        "ffff000000000003",
                        "ACME CORP",
                        -18.30,
                        txn_date="2025-12-31",
                        category="Shopping",
                    ),
                ]
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Work:Subscriptions",
                workspace=workspace,
                date_from=date(2025, 3, 1),
                date_to=date(2025, 9, 30),
                write=True,
            )
            assert rc == 0

            ledger = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            by_id = {g.primary.transaction_id: g for g in ledger}
            # Jan 1 is before window — must be unchanged
            assert by_id["ffff000000000001"].primary.category == "Shopping"
            # Jun 15 is inside window — must be recategorized
            assert by_id["ffff000000000002"].primary.category == "Work"
            assert by_id["ffff000000000002"].primary.subcategory == "Subscriptions"
            # Dec 31 is after window — must be unchanged
            assert by_id["ffff000000000003"].primary.category == "Shopping"

    def it_should_select_by_fy(self):
        """FY range filter includes transactions inside the fiscal year; excludes those outside."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    # FY25 = Nov 1 2024 – Oct 31 2025
                    _make_txn(
                        "gggg000000000001",
                        "ACME CORP",
                        -18.30,
                        txn_date="2024-11-01",
                        category="Shopping",
                    ),
                    _make_txn(
                        "gggg000000000002",
                        "ACME CORP",
                        -18.30,
                        txn_date="2025-05-01",
                        category="Shopping",
                    ),
                    _make_txn(
                        "gggg000000000003",
                        "ACME CORP",
                        -18.30,
                        txn_date="2025-11-01",
                        category="Shopping",
                    ),
                ]
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            from gilt.util.fy import fiscal_year_range

            rc = run(
                to_category="Work:Subscriptions",
                workspace=workspace,
                fy_range=fiscal_year_range("FY25"),
                write=True,
            )
            assert rc == 0

            ledger = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            by_id = {g.primary.transaction_id: g for g in ledger}
            # Nov 1 2024 is first day of FY25 — inside window
            assert by_id["gggg000000000001"].primary.category == "Work"
            assert by_id["gggg000000000001"].primary.subcategory == "Subscriptions"
            # May 1 2025 is inside FY25
            assert by_id["gggg000000000002"].primary.category == "Work"
            assert by_id["gggg000000000002"].primary.subcategory == "Subscriptions"
            # Nov 1 2025 is the first day of FY26 — outside FY25
            assert by_id["gggg000000000003"].primary.category == "Shopping"


# ---------------------------------------------------------------------------
# Selection mode — combined filters
# ---------------------------------------------------------------------------


class DescribeSelectionModeCombined:
    """Combined filter scenarios."""

    def it_should_combine_desc_prefix_amount_and_account(self):
        """The canonical 'Microsoft $18.30 on CC' scenario: desc + amount + account."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "MYBANK_CHQ": [
                    _make_txn(
                        "hhhh000000000001",
                        "ACME CORP subscription",
                        -18.30,
                        account_id="MYBANK_CHQ",
                        category="Entertainment",
                    ),
                ],
                "MYBANK_CC": [
                    _make_txn(
                        "hhhh000000000002",
                        "ACME CORP subscription",
                        -18.30,
                        account_id="MYBANK_CC",
                        category="Entertainment",
                    ),
                    _make_txn(
                        "hhhh000000000003",
                        "ACME CORP other",
                        -99.00,
                        account_id="MYBANK_CC",
                        category="Entertainment",
                    ),
                ],
            }
            workspace, _ = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Work:Subscriptions",
                workspace=workspace,
                desc_prefix="ACME CORP subscription",
                amount_eq=-18.30,
                account="MYBANK_CC",
                write=False,
            )
            assert rc == 0

    def it_should_change_category_when_selection_only(self):
        """--to works without --from in selection mode."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    _make_txn("iiii000000000001", "EXAMPLE UTILITY", -75.00, category="Housing"),
                    _make_txn("iiii000000000002", "SAMPLE STORE", -40.00, category="Shopping"),
                ]
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Housing:Utilities",
                workspace=workspace,
                desc_prefix="EXAMPLE UTILITY",
                write=True,
            )
            assert rc == 0

            ledger = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            by_id = {g.primary.transaction_id: g for g in ledger}
            assert by_id["iiii000000000001"].primary.category == "Housing"
            assert by_id["iiii000000000001"].primary.subcategory == "Utilities"
            # Unrelated transaction unchanged
            assert by_id["iiii000000000002"].primary.category == "Shopping"

    def it_should_intersect_from_with_selection_filters(self):
        """--from restricts the selection: only transactions with that category get updated."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    _make_txn("jjjj000000000001", "ACME CORP", -18.30, category="Entertainment"),
                    _make_txn("jjjj000000000002", "ACME CORP", -18.30, category="Shopping"),
                ]
            }
            workspace, data_dir = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Work:Subscriptions",
                workspace=workspace,
                from_category="Entertainment",
                account="TEST",
                write=True,
            )
            assert rc == 0

            ledger = load_ledger_csv((data_dir / "TEST.csv").read_text(), default_currency="CAD")
            by_id = {g.primary.transaction_id: g for g in ledger}
            assert by_id["jjjj000000000001"].primary.category == "Work"
            assert by_id["jjjj000000000001"].primary.subcategory == "Subscriptions"
            # Different original category — must be untouched
            assert by_id["jjjj000000000002"].primary.category == "Shopping"


# ---------------------------------------------------------------------------
# Validation / mutual exclusivity
# ---------------------------------------------------------------------------


class DescribeSelectionModeValidation:
    """Validation rules for selection flags."""

    def _workspace(self, tmpdir: str) -> Workspace:
        data_dir = Path(tmpdir) / "data" / "accounts"
        data_dir.mkdir(parents=True)
        return Workspace(root=Path(tmpdir))

    def it_should_error_when_desc_prefix_and_pattern_both_set(self):
        with TemporaryDirectory() as tmpdir:
            workspace = self._workspace(tmpdir)
            rc = run(
                to_category="Work",
                workspace=workspace,
                desc_prefix="ACME",
                pattern=r"ACME.*",
                write=False,
            )
            assert rc == 1

    def it_should_error_when_amount_eq_combined_with_min_or_max(self):
        with TemporaryDirectory() as tmpdir:
            workspace = self._workspace(tmpdir)
            rc = run(
                to_category="Work",
                workspace=workspace,
                amount_eq=-18.30,
                amount_min=-20.00,
                write=False,
            )
            assert rc == 1

    def it_should_error_when_no_from_and_no_selection(self):
        """Without --from and without selection flags, the command must error."""
        with TemporaryDirectory() as tmpdir:
            workspace = self._workspace(tmpdir)
            rc = run(
                to_category="Work",
                workspace=workspace,
                from_category=None,
                write=False,
            )
            assert rc == 1

    def it_should_not_error_when_selection_only_and_no_from(self):
        """Selection mode with --to but no --from is valid."""
        with TemporaryDirectory() as tmpdir:
            groups = {
                "TEST": [
                    _make_txn("kkkk000000000001", "ACME CORP", -18.30, category="Entertainment"),
                ]
            }
            workspace, _ = _setup_workspace(tmpdir, groups)

            rc = run(
                to_category="Work",
                workspace=workspace,
                account="TEST",
                write=False,
            )
            assert rc == 0


# ---------------------------------------------------------------------------
# Typer-layer (CLI runner) tests
# ---------------------------------------------------------------------------


class DescribeRecategorizeCLI:
    """Integration tests via Typer CliRunner."""

    def it_should_error_on_invalid_date_from(self):
        from gilt.cli.app import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["recategorize", "--to", "Work", "--date-from", "not-a-date"],
            catch_exceptions=False,
        )
        assert result.exit_code != 0

    def it_should_error_when_fy_and_date_from_both_set(self):
        from gilt.cli.app import app

        runner = CliRunner()
        result = runner.invoke(
            app,
            ["recategorize", "--to", "Work", "--fy", "FY25", "--date-from", "2025-01-01"],
            catch_exceptions=False,
        )
        assert result.exit_code != 0
