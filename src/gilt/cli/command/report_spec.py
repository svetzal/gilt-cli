from __future__ import annotations

"""
Tests for report command CLI wiring.

Business logic tests (aggregation, markdown rendering) live in:
    src/gilt/services/budget_reporting_service_spec.py
"""

from unittest.mock import patch

import pytest

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.report import run
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig
from gilt.testing import build_workspace_with_ledger, make_group


class DescribeReportCommand:
    """Tests for the report command CLI wiring."""

    def it_should_generate_markdown_in_dry_run(self, tmp_path):
        """Should display dry-run message and preview without writing files."""
        config = CategoryConfig(
            categories=[
                Category(
                    name="Housing",
                    budget=Budget(amount=2500.00, period=BudgetPeriod.monthly),
                ),
            ]
        )
        workspace = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="test1",
                    date="2025-10-01",
                    description="Mortgage",
                    amount=-1500.00,
                    account_id="MYBANK_CHQ",
                    category="Housing",
                ),
            ],
            config=config,
            projections=False,
        )

        result = run(
            year=2025,
            month=10,
            output=workspace.root / "reports" / "test_report",
            workspace=workspace,
            write=False,
        )

        assert result == 0
        assert not (workspace.root / "reports" / "test_report.md").exists()
        assert not (workspace.root / "reports" / "test_report.docx").exists()

    def it_should_write_markdown_file_with_write_flag(self, tmp_path):
        """Should write markdown file with write flag."""
        config = CategoryConfig(
            categories=[
                Category(
                    name="Groceries",
                    budget=Budget(amount=600.00, period=BudgetPeriod.monthly),
                ),
            ]
        )
        workspace = build_workspace_with_ledger(
            tmp_path,
            groups=[
                make_group(
                    transaction_id="test1",
                    date="2025-10-05",
                    description="SAMPLE STORE",
                    amount=-250.00,
                    account_id="MYBANK_CHQ",
                    category="Groceries",
                ),
            ],
            config=config,
            projections=True,
        )

        with patch("gilt.cli.command.report._check_pandoc", return_value=False):
            result = run(
                year=2025,
                month=10,
                output=workspace.root / "reports" / "test_report",
                workspace=workspace,
                write=True,
            )

        assert result == 0

        md_path = workspace.root / "reports" / "test_report.md"
        assert md_path.exists()

        content = md_path.read_text(encoding="utf-8")
        assert "# Budget Report - 2025-10" in content
        assert "Groceries" in content
        assert "$600.00" in content
        assert "$250.00" in content

    def it_should_error_when_month_without_year(self, tmp_path):
        """Should return error when month is specified without year."""
        workspace = build_workspace_with_ledger(tmp_path, config=CategoryConfig(categories=[]))

        with pytest.raises(CommandAbort) as exc_info:
            run(
                year=None,
                month=10,
                workspace=workspace,
                write=False,
            )

        assert exc_info.value.code == 1

    def it_should_error_on_invalid_month(self, tmp_path):
        """Should return error when month is out of range."""
        workspace = build_workspace_with_ledger(tmp_path, config=CategoryConfig(categories=[]))

        with pytest.raises(CommandAbort) as exc_info:
            run(
                year=2025,
                month=13,
                workspace=workspace,
                write=False,
            )

        assert exc_info.value.code == 1
