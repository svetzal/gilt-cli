from __future__ import annotations

"""
Specs for the ingest CLI command helper functions and dry-run behaviour.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from pathlib import Path
from tempfile import TemporaryDirectory

from gilt.cli.command.ingest import (
    _load_ledger_counts,
    run,
)
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.ledger_io import dump_ledger_csv
from gilt.workspace import Workspace

# ---------------------------------------------------------------------------
# Note: _ledger_paths_to_load behaviour is tested in
#       ingestion_service_spec.py::DescribeDiscoverLedgerPaths
# ---------------------------------------------------------------------------


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
