from __future__ import annotations

"""
Specs for the ingest CLI command helper functions and dry-run behaviour.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.ingest import (
    _amount_sign_for,
    _ledger_paths_to_load,
    _load_ledger_counts,
    run,
)
from gilt.model.account import Account, ImportHints, Transaction, TransactionGroup
from gilt.model.ledger_io import dump_ledger_csv
from gilt.workspace import Workspace

# ---------------------------------------------------------------------------
# _amount_sign_for
# ---------------------------------------------------------------------------


class DescribeAmountSignFor:
    """Specs for looking up the amount_sign hint for a given account."""

    def it_should_return_expenses_negative_when_no_accounts_given(self):
        result = _amount_sign_for("MYBANK_CHQ", [])
        assert result == "expenses_negative"

    def it_should_return_expenses_negative_for_unknown_account_id(self):
        account = Account(
            account_id="MYBANK_CHQ",
            import_hints=ImportHints(amount_sign="expenses_positive"),
        )
        result = _amount_sign_for("BANK2_BIZ", [account])
        assert result == "expenses_negative"

    def it_should_return_configured_amount_sign_for_matching_account(self):
        account = Account(
            account_id="MYBANK_CC",
            import_hints=ImportHints(amount_sign="expenses_positive"),
        )
        result = _amount_sign_for("MYBANK_CC", [account])
        assert result == "expenses_positive"

    def it_should_return_expenses_negative_when_account_has_no_import_hints(self):
        account = Account(account_id="MYBANK_CC")
        result = _amount_sign_for("MYBANK_CC", [account])
        assert result == "expenses_negative"

    def it_should_return_expenses_negative_when_amount_sign_hint_is_none(self):
        account = Account(
            account_id="MYBANK_CC",
            import_hints=ImportHints(amount_sign=None),
        )
        result = _amount_sign_for("MYBANK_CC", [account])
        assert result == "expenses_negative"


# ---------------------------------------------------------------------------
# _ledger_paths_to_load
# ---------------------------------------------------------------------------


class DescribeLedgerPathsToLoad:
    """Specs for resolving which existing ledger CSVs should be loaded."""

    def it_should_return_empty_list_when_output_dir_has_no_csvs(self):
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            result = _ledger_paths_to_load(output_dir, [])
            assert result == []

    def it_should_include_configured_account_csv_when_it_exists(self):
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            account = Account(account_id="MYBANK_CHQ")
            # Create the file
            (output_dir / "MYBANK_CHQ.csv").write_text("header\n", encoding="utf-8")
            result = _ledger_paths_to_load(output_dir, [account])
            assert any(p.name == "MYBANK_CHQ.csv" for p in result)

    def it_should_not_include_configured_account_csv_when_file_absent(self):
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            account = Account(account_id="MYBANK_CHQ")
            # File does NOT exist
            result = _ledger_paths_to_load(output_dir, [account])
            assert not any(p.name == "MYBANK_CHQ.csv" for p in result)

    def it_should_include_additional_csvs_not_covered_by_configured_accounts(self):
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            account = Account(account_id="MYBANK_CHQ")
            (output_dir / "MYBANK_CHQ.csv").write_text("header\n", encoding="utf-8")
            # An extra CSV not in accounts config
            (output_dir / "BANK2_BIZ.csv").write_text("header\n", encoding="utf-8")
            result = _ledger_paths_to_load(output_dir, [account])
            names = {p.name for p in result}
            assert "MYBANK_CHQ.csv" in names
            assert "BANK2_BIZ.csv" in names

    def it_should_not_duplicate_a_csv_that_is_both_configured_and_present(self):
        with TemporaryDirectory() as tmpdir:
            output_dir = Path(tmpdir)
            account = Account(account_id="MYBANK_CHQ")
            (output_dir / "MYBANK_CHQ.csv").write_text("header\n", encoding="utf-8")
            result = _ledger_paths_to_load(output_dir, [account])
            names = [p.name for p in result]
            assert names.count("MYBANK_CHQ.csv") == 1


# ---------------------------------------------------------------------------
# _load_ledger_counts
# ---------------------------------------------------------------------------


class DescribeLoadLedgerCounts:
    """Specs for counting transaction groups in ledger CSV files."""

    def it_should_return_empty_dict_for_no_paths(self):
        result = _load_ledger_counts([])
        assert result == {}

    def it_should_count_groups_per_file(self):
        with TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir)
            groups = [
                TransactionGroup(
                    group_id=f"g{i}",
                    primary=Transaction(
                        transaction_id=f"txid{i:012d}",
                        date="2025-01-10",
                        description="SAMPLE STORE",
                        amount=-25.0,
                        currency="CAD",
                        account_id="MYBANK_CHQ",
                    ),
                )
                for i in range(3)
            ]
            ledger_path = data_dir / "MYBANK_CHQ.csv"
            ledger_path.write_text(dump_ledger_csv(groups), encoding="utf-8")

            result = _load_ledger_counts([ledger_path])
            assert result["MYBANK_CHQ.csv"] == 3

    def it_should_return_zero_count_for_unreadable_file(self):
        # A path that doesn't exist behaves as an unreadable file
        with TemporaryDirectory() as tmpdir:
            missing = Path(tmpdir) / "missing.csv"
            result = _load_ledger_counts([missing])
            assert result["missing.csv"] == 0


# ---------------------------------------------------------------------------
# run — dry-run mode
# ---------------------------------------------------------------------------


class DescribeIngestRunDryRun:
    """Specs for the ingest command run() in dry-run mode."""

    def it_should_return_zero_with_empty_ingest_dir(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ingest_dir.mkdir(parents=True, exist_ok=True)

            result = run(workspace=ws, write=False)
            assert result == 0

    def it_should_not_create_any_output_files_in_dry_run(self):
        with TemporaryDirectory() as tmpdir:
            ws = Workspace(root=Path(tmpdir))
            ws.ingest_dir.mkdir(parents=True, exist_ok=True)
            # Put a dummy CSV in ingest to give the planner something to see
            ingest_csv = ws.ingest_dir / "mybank_export.csv"
            ingest_csv.write_text(
                "Date,Description,Amount\n2025-01-10,SAMPLE STORE,-25.00\n",
                encoding="utf-8",
            )

            run(workspace=ws, write=False)

            # Output directory should not have been created
            assert not ws.ledger_data_dir.exists()
