from __future__ import annotations

"""
Tests for recategorize command.
"""

from datetime import date
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.recategorize import build_date_selection, run
from gilt.model.ledger_io import load_ledger_csv
from gilt.testing import build_workspace_with_ledger, make_group, make_workspace, write_ledger

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _setup_workspace(tmp_path: Path, groups_by_account: dict[str, list]):
    """Write ledgers and build projections. Returns workspace and data_dir."""
    ws = build_workspace_with_ledger(tmp_path, projections=False)
    for account_id, groups in groups_by_account.items():
        write_ledger(ws.ledger_data_dir / f"{account_id}.csv", groups)
    from gilt.testing import build_projections_from_csvs

    build_projections_from_csvs(ws.ledger_data_dir, ws.projections_path)
    return ws, ws.ledger_data_dir


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

    def it_should_rename_category_preserving_subcategories(self, tmp_path):
        """Test that renaming only the parent category preserves existing subcategories."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="1111111111111111",
                        date=date(2025, 1, 1),
                        description="Bank Fee",
                        amount=-46.0,
                        account_id="TEST",
                        category="Business",
                        subcategory="Bank Fees",
                    ),
                    make_group(
                        transaction_id="2222222222222222",
                        date=date(2025, 1, 2),
                        description="Loan Payment",
                        amount=-500.0,
                        account_id="TEST",
                        category="Business",
                        subcategory="Loan",
                    ),
                    make_group(
                        transaction_id="3333333333333333",
                        date=date(2025, 1, 3),
                        description="Subscription",
                        amount=-50.0,
                        account_id="TEST",
                        category="Business",
                        subcategory="Subscriptions",
                    ),
                ]
            },
        )
        ledger_path = data_dir / "TEST.csv"

        # Dry-run should not modify
        rc = run(
            from_category="Business",
            to_category="Work",
            workspace=ws,
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
            workspace=ws,
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

    def it_should_rename_specific_subcategory(self, tmp_path):
        """Test that specifying both category and subcategory renames only that subcategory."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="1111111111111111",
                        date=date(2025, 1, 1),
                        description="Bank Fee",
                        amount=-46.0,
                        account_id="TEST",
                        category="Business",
                        subcategory="Bank Fees",
                    ),
                    make_group(
                        transaction_id="2222222222222222",
                        date=date(2025, 1, 2),
                        description="Loan Payment",
                        amount=-500.0,
                        account_id="TEST",
                        category="Business",
                        subcategory="Loan",
                    ),
                ]
            },
        )
        ledger_path = data_dir / "TEST.csv"

        # Rename only Business:Bank Fees to Work:Bank Fees
        rc = run(
            from_category="Business:Bank Fees",
            to_category="Work:Bank Fees",
            workspace=ws,
            write=True,
        )
        assert rc == 0

        groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
        assert groups[0].primary.category == "Work"
        assert groups[0].primary.subcategory == "Bank Fees"
        # Second transaction should remain unchanged
        assert groups[1].primary.category == "Business"
        assert groups[1].primary.subcategory == "Loan"

    def it_should_rename_category_without_subcategory(self, tmp_path):
        """Test renaming a category that has no subcategories."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="1111111111111111",
                        date=date(2025, 1, 1),
                        description="Misc Expense",
                        amount=-100.0,
                        account_id="TEST",
                        category="Miscellaneous",
                    ),
                ]
            },
        )
        ledger_path = data_dir / "TEST.csv"

        rc = run(
            from_category="Miscellaneous",
            to_category="Other",
            workspace=ws,
            write=True,
        )
        assert rc == 0

        groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
        assert groups[0].primary.category == "Other"
        assert groups[0].primary.subcategory is None

    def it_should_return_zero_when_no_matches(self, tmp_path):
        """Test that command returns 0 when no transactions match."""
        ws, _ = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="1111111111111111",
                        date=date(2025, 1, 1),
                        description="Test",
                        amount=-100.0,
                        account_id="TEST",
                        category="Housing",
                    ),
                ]
            },
        )

        rc = run(
            from_category="NonExistent",
            to_category="Other",
            workspace=ws,
            write=False,
        )
        assert rc == 0

    def it_should_work_across_multiple_accounts(self, tmp_path):
        """Test that renaming works across multiple ledger files."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                account: [
                    make_group(
                        transaction_id=f"{account}1111111111",
                        date=date(2025, 1, 1),
                        description="Business Expense",
                        amount=-100.0,
                        account_id=account,
                        category="Business",
                        subcategory="Supplies",
                    )
                ]
                for account in ["ACCOUNT1", "ACCOUNT2"]
            },
        )

        rc = run(
            from_category="Business",
            to_category="Work",
            workspace=ws,
            write=True,
        )
        assert rc == 0

        # Verify both accounts updated
        for account in ["ACCOUNT1", "ACCOUNT2"]:
            ledger_path = data_dir / f"{account}.csv"
            groups = load_ledger_csv(ledger_path.read_text(), default_currency="CAD")
            assert groups[0].primary.category == "Work"
            assert groups[0].primary.subcategory == "Supplies"

    def it_should_error_on_empty_from_category(self, tmp_path):
        """Test that empty --from category returns error."""
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])

        with pytest.raises(CommandAbort) as exc_info:
            run(
                from_category="",
                to_category="Other",
                workspace=ws,
                write=False,
            )
        assert exc_info.value.code == 1

    def it_should_error_on_empty_to_category(self, tmp_path):
        """Test that empty --to category returns error."""
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])

        with pytest.raises(CommandAbort) as exc_info:
            run(
                from_category="Business",
                to_category="",
                workspace=ws,
                write=False,
            )
        assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# Selection mode — individual filter tests
# ---------------------------------------------------------------------------


class DescribeSelectionModeFilters:
    """Selection mode tests: each filter criterion in isolation."""

    def it_should_select_by_desc_prefix(self, tmp_path):
        """Transactions whose description starts with the prefix are selected; others unchanged."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="aaaa000000000001",
                        description="ACME CORP subscription",
                        amount=-18.30,
                        account_id="TEST",
                        category="Entertainment",
                    ),
                    make_group(
                        transaction_id="aaaa000000000002",
                        description="SAMPLE STORE groceries",
                        amount=-42.00,
                        account_id="TEST",
                        category="Groceries",
                    ),
                ]
            },
        )

        rc = run(
            to_category="Work:Subscriptions",
            workspace=ws,
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

    def it_should_select_by_pattern(self, tmp_path):
        """Transactions matching the regex pattern are selected; others unchanged."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="bbbb000000000001",
                        description="EXAMPLE UTILITY electric bill",
                        amount=-120.00,
                        account_id="TEST",
                        category="Housing",
                    ),
                    make_group(
                        transaction_id="bbbb000000000002",
                        description="ACME CORP purchase",
                        amount=-55.00,
                        account_id="TEST",
                        category="Shopping",
                    ),
                ]
            },
        )

        rc = run(
            to_category="Housing:Utilities",
            workspace=ws,
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

    def it_should_select_by_amount_eq(self, tmp_path):
        """Only the exact signed amount matches: -18.30 debit is selected, +18.30 credit is not."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="cccc000000000001",
                        description="ACME CORP",
                        amount=-18.30,
                        account_id="TEST",
                        category="Entertainment",
                    ),
                    make_group(
                        transaction_id="cccc000000000002",
                        description="REFUND ACME",
                        amount=18.30,
                        account_id="TEST",
                        category="Income",
                    ),
                    make_group(
                        transaction_id="cccc000000000003",
                        description="ACME CORP",
                        amount=-99.00,
                        account_id="TEST",
                        category="Entertainment",
                    ),
                ]
            },
        )

        rc = run(
            to_category="Work:Subscriptions",
            workspace=ws,
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

    def it_should_select_by_amount_min_and_max(self, tmp_path):
        """Transactions with amount in [min, max] are selected; outside that range are not."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="dddd000000000001",
                        description="SAMPLE STORE",
                        amount=-10.00,
                        account_id="TEST",
                        category="Shopping",
                    ),
                    make_group(
                        transaction_id="dddd000000000002",
                        description="SAMPLE STORE",
                        amount=-50.00,
                        account_id="TEST",
                        category="Shopping",
                    ),
                    make_group(
                        transaction_id="dddd000000000003",
                        description="SAMPLE STORE",
                        amount=-200.00,
                        account_id="TEST",
                        category="Shopping",
                    ),
                ]
            },
        )

        rc = run(
            to_category="Groceries",
            workspace=ws,
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

    def it_should_select_by_account(self, tmp_path):
        """Only transactions in the specified account are selected; other accounts unchanged."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "MYBANK_CHQ": [
                    make_group(
                        transaction_id="eeee000000000001",
                        description="ACME CORP",
                        amount=-18.30,
                        account_id="MYBANK_CHQ",
                        category="Entertainment",
                    ),
                ],
                "MYBANK_CC": [
                    make_group(
                        transaction_id="eeee000000000002",
                        description="ACME CORP",
                        amount=-18.30,
                        account_id="MYBANK_CC",
                        category="Entertainment",
                    ),
                ],
            },
        )

        rc = run(
            to_category="Work:Subscriptions",
            workspace=ws,
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

    def it_should_select_by_date_from_and_date_to(self, tmp_path):
        """Only transactions within the date window are selected; outside dates are unchanged."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="ffff000000000001",
                        description="ACME CORP",
                        amount=-18.30,
                        date=date(2025, 1, 1),
                        account_id="TEST",
                        category="Shopping",
                    ),
                    make_group(
                        transaction_id="ffff000000000002",
                        description="ACME CORP",
                        amount=-18.30,
                        date=date(2025, 6, 15),
                        account_id="TEST",
                        category="Shopping",
                    ),
                    make_group(
                        transaction_id="ffff000000000003",
                        description="ACME CORP",
                        amount=-18.30,
                        date=date(2025, 12, 31),
                        account_id="TEST",
                        category="Shopping",
                    ),
                ]
            },
        )

        rc = run(
            to_category="Work:Subscriptions",
            workspace=ws,
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

    def it_should_select_by_fy(self, tmp_path):
        """FY range filter includes transactions inside the fiscal year; excludes those outside."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    # FY25 = Nov 1 2024 – Oct 31 2025
                    make_group(
                        transaction_id="gggg000000000001",
                        description="ACME CORP",
                        amount=-18.30,
                        date=date(2024, 11, 1),
                        account_id="TEST",
                        category="Shopping",
                    ),
                    make_group(
                        transaction_id="gggg000000000002",
                        description="ACME CORP",
                        amount=-18.30,
                        date=date(2025, 5, 1),
                        account_id="TEST",
                        category="Shopping",
                    ),
                    make_group(
                        transaction_id="gggg000000000003",
                        description="ACME CORP",
                        amount=-18.30,
                        date=date(2025, 11, 1),
                        account_id="TEST",
                        category="Shopping",
                    ),
                ]
            },
        )

        from gilt.util.fy import fiscal_year_range

        rc = run(
            to_category="Work:Subscriptions",
            workspace=ws,
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

    def it_should_combine_desc_prefix_amount_and_account(self, tmp_path):
        """The canonical 'Microsoft $18.30 on CC' scenario: desc + amount + account."""
        ws, _ = _setup_workspace(
            tmp_path,
            {
                "MYBANK_CHQ": [
                    make_group(
                        transaction_id="hhhh000000000001",
                        description="ACME CORP subscription",
                        amount=-18.30,
                        account_id="MYBANK_CHQ",
                        category="Entertainment",
                    ),
                ],
                "MYBANK_CC": [
                    make_group(
                        transaction_id="hhhh000000000002",
                        description="ACME CORP subscription",
                        amount=-18.30,
                        account_id="MYBANK_CC",
                        category="Entertainment",
                    ),
                    make_group(
                        transaction_id="hhhh000000000003",
                        description="ACME CORP other",
                        amount=-99.00,
                        account_id="MYBANK_CC",
                        category="Entertainment",
                    ),
                ],
            },
        )

        rc = run(
            to_category="Work:Subscriptions",
            workspace=ws,
            desc_prefix="ACME CORP subscription",
            amount_eq=-18.30,
            account="MYBANK_CC",
            write=False,
        )
        assert rc == 0

    def it_should_change_category_when_selection_only(self, tmp_path):
        """--to works without --from in selection mode."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="iiii000000000001",
                        description="EXAMPLE UTILITY",
                        amount=-75.00,
                        account_id="TEST",
                        category="Housing",
                    ),
                    make_group(
                        transaction_id="iiii000000000002",
                        description="SAMPLE STORE",
                        amount=-40.00,
                        account_id="TEST",
                        category="Shopping",
                    ),
                ]
            },
        )

        rc = run(
            to_category="Housing:Utilities",
            workspace=ws,
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

    def it_should_intersect_from_with_selection_filters(self, tmp_path):
        """--from restricts the selection: only transactions with that category get updated."""
        ws, data_dir = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="jjjj000000000001",
                        description="ACME CORP",
                        amount=-18.30,
                        account_id="TEST",
                        category="Entertainment",
                    ),
                    make_group(
                        transaction_id="jjjj000000000002",
                        description="ACME CORP",
                        amount=-18.30,
                        account_id="TEST",
                        category="Shopping",
                    ),
                ]
            },
        )

        rc = run(
            to_category="Work:Subscriptions",
            workspace=ws,
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

    def it_should_error_when_desc_prefix_and_pattern_both_set(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        with pytest.raises(CommandAbort) as exc_info:
            run(
                to_category="Work",
                workspace=ws,
                desc_prefix="ACME",
                pattern=r"ACME.*",
                write=False,
            )
        assert exc_info.value.code == 1

    def it_should_error_when_amount_eq_combined_with_min_or_max(self, tmp_path):
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        with pytest.raises(CommandAbort) as exc_info:
            run(
                to_category="Work",
                workspace=ws,
                amount_eq=-18.30,
                amount_min=-20.00,
                write=False,
            )
        assert exc_info.value.code == 1

    def it_should_error_when_no_from_and_no_selection(self, tmp_path):
        """Without --from and without selection flags, the command must error."""
        ws = make_workspace(tmp_path, init_dirs=["ledger_data_dir"])
        with pytest.raises(CommandAbort) as exc_info:
            run(
                to_category="Work",
                workspace=ws,
                from_category=None,
                write=False,
            )
        assert exc_info.value.code == 1

    def it_should_not_error_when_selection_only_and_no_from(self, tmp_path):
        """Selection mode with --to but no --from is valid."""
        ws, _ = _setup_workspace(
            tmp_path,
            {
                "TEST": [
                    make_group(
                        transaction_id="kkkk000000000001",
                        description="ACME CORP",
                        amount=-18.30,
                        account_id="TEST",
                        category="Entertainment",
                    ),
                ]
            },
        )

        rc = run(
            to_category="Work",
            workspace=ws,
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
