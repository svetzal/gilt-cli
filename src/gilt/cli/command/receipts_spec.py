from __future__ import annotations

"""
Tests for the receipts CLI command.
"""

from datetime import date

import pytest
from rich.console import Console

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.receipts import run
from gilt.model.events import TransactionEnriched
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.testing import build_workspace_with_ledger, make_group
from gilt.workspace import Workspace


def _attach_receipt(workspace: Workspace, transaction_id: str, receipt_file: str) -> None:
    """Attach a receipt to a transaction via a TransactionEnriched event."""
    store = EventStore(str(workspace.event_store_path))
    evt = TransactionEnriched(
        transaction_id=transaction_id,
        vendor="ACME CORP",
        receipt_file=receipt_file,
        enrichment_source="test",
    )
    store.append_event(evt)
    builder = ProjectionBuilder(workspace.projections_path)
    builder.build_incremental(store)


def _run_capturing(workspace: Workspace, **kwargs) -> tuple[int, str]:
    """Run the command with a record-capturing console; return (rc, output)."""
    cap = Console(record=True, width=200)
    rc = run(workspace=workspace, _console=cap, **kwargs)
    return rc, cap.export_text()


class DescribeReceiptsCommand:
    """Tests for the receipts command."""

    def it_should_show_summary_table_for_mojility_transactions(self, tmp_path):
        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-02-10",
                description="Sample consulting",
                amount=-500.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
            make_group(
                transaction_id="2222222222222222",
                date="2025-03-05",
                description="Software license",
                amount=-100.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Software",
            ),
        ]
        workspace = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)
        _attach_receipt(workspace, "1111111111111111", "inv-001.pdf")

        rc, output = _run_capturing(workspace)

        assert rc == 0
        assert "Receipt Coverage" in output
        assert "Consulting" in output
        assert "Software" in output

    def it_should_compute_coverage_counts_correctly(self, tmp_path):
        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-01-10",
                description="Consulting A",
                amount=-200.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
            make_group(
                transaction_id="2222222222222222",
                date="2025-01-20",
                description="Consulting B",
                amount=-300.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
        ]
        workspace = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)
        _attach_receipt(workspace, "1111111111111111", "inv-a.pdf")

        rc, output = _run_capturing(workspace)

        assert rc == 0
        # 2 total, 1 with receipt
        assert "2" in output
        assert "50%" in output

    def it_should_group_by_account_when_by_account_flag_set(self, tmp_path):
        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-01-10",
                description="Consulting via CC",
                amount=-200.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
            make_group(
                transaction_id="2222222222222222",
                date="2025-01-20",
                description="Consulting via Biz",
                amount=-300.0,
                account_id="BANK2_BIZ",
                category="Mojility",
                subcategory="Consulting",
            ),
        ]
        workspace = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)

        rc, output = _run_capturing(workspace, by_account=True)

        assert rc == 0
        assert "MYBANK_CC" in output
        assert "BANK2_BIZ" in output
        assert "account_id" in output

    def it_should_filter_by_fy_range(self, tmp_path):
        groups = [
            # Inside FY25 (Nov 1 2024 – Oct 31 2025)
            make_group(
                transaction_id="1111111111111111",
                date="2025-03-15",
                description="In-range consulting",
                amount=-400.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
            # Outside FY25
            make_group(
                transaction_id="2222222222222222",
                date="2025-11-10",
                description="Out-of-range consulting",
                amount=-600.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
        ]
        workspace = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)

        fy_range = (date(2024, 11, 1), date(2025, 10, 31))
        rc, output = _run_capturing(workspace, fy_range=fy_range, fy_label="FY25")

        assert rc == 0
        assert "FY25" in output
        # Only 1 transaction in FY25
        assert "1" in output

    def it_should_list_missing_receipts_with_missing_flag(self, tmp_path):
        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-02-01",
                description="Invoice 123",
                amount=-250.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
            make_group(
                transaction_id="2222222222222222",
                date="2025-02-15",
                description="Invoice 456",
                amount=-350.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
        ]
        workspace = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)
        _attach_receipt(workspace, "2222222222222222", "inv-456.pdf")

        rc, output = _run_capturing(workspace, missing=True)

        assert rc == 0
        assert "Transactions Without Receipts" in output
        # txn 1 has no receipt; txn 2 has one → only txn 1 appears
        assert "11111111" in output
        assert "22222222" not in output
        assert "Invoice 123" in output

    def it_should_show_success_message_when_all_have_receipts(self, tmp_path):
        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-02-01",
                description="Fully receipted",
                amount=-100.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
        ]
        workspace = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)
        _attach_receipt(workspace, "1111111111111111", "inv.pdf")

        rc, output = _run_capturing(workspace, missing=True)

        assert rc == 0
        assert "All matching transactions have receipts" in output

    def it_should_use_category_override(self, tmp_path):
        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-05-01",
                description="Food purchase",
                amount=-60.0,
                account_id="MYBANK_CHQ",
                category="Food",
                subcategory="Groceries",
            ),
            make_group(
                transaction_id="2222222222222222",
                date="2025-05-10",
                description="Consulting work",
                amount=-500.0,
                account_id="MYBANK_CC",
                category="Mojility",
                subcategory="Consulting",
            ),
        ]
        workspace = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)

        rc, output = _run_capturing(workspace, category="Food")

        assert rc == 0
        assert "Food" in output
        assert "Groceries" in output
        # Mojility transactions should NOT appear
        assert "Consulting" not in output

    def it_should_handle_empty_mojility_gracefully(self, tmp_path):
        groups = [
            make_group(
                transaction_id="1111111111111111",
                date="2025-01-01",
                description="Grocery run",
                amount=-80.0,
                account_id="MYBANK_CHQ",
                category="Food",
            ),
        ]
        workspace = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)

        rc, output = _run_capturing(workspace)  # default category="Mojility"

        assert rc == 0
        assert "No" in output
        assert "Mojility" in output

    def it_should_return_error_when_projections_missing(self, tmp_path):
        workspace = Workspace(root=tmp_path)
        # Do NOT build projections

        cap = Console(record=True)
        with pytest.raises(CommandAbort) as exc_info:
            run(workspace=workspace, _console=cap)

        assert exc_info.value.code == 1
