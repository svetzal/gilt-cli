from __future__ import annotations

"""
Tests for report command CLI wiring.

Business logic tests (aggregation, markdown rendering) live in:
    src/gilt/services/budget_reporting_service_spec.py
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from gilt.cli.command.conftest import build_projections_from_csvs, write_ledger
from gilt.cli.command.report import run
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.category import Budget, BudgetPeriod, Category, CategoryConfig
from gilt.model.category_io import save_categories_config
from gilt.workspace import Workspace


class DescribeReportCommand:
    """Tests for the report command CLI wiring."""

    def it_should_generate_markdown_in_dry_run(self):
        """Should display dry-run message and preview without writing files."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_dir = tmp / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = tmp / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=tmp)

            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        budget=Budget(amount=2500.00, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)

            ledger_path = data_dir / "test.csv"
            write_ledger(
                ledger_path,
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id="test1",
                            date="2025-10-01",
                            description="Mortgage",
                            amount=-1500.00,
                            currency="CAD",
                            account_id="MYBANK_CHQ",
                            category="Housing",
                        ),
                    ),
                ],
            )

            result = run(
                year=2025,
                month=10,
                output=tmp / "reports" / "test_report",
                workspace=workspace,
                write=False,
            )

            assert result == 0
            assert not (tmp / "reports" / "test_report.md").exists()
            assert not (tmp / "reports" / "test_report.docx").exists()

    def it_should_write_markdown_file_with_write_flag(self):
        """Should write markdown file with write flag."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_dir = tmp / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = tmp / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=tmp)

            config = CategoryConfig(
                categories=[
                    Category(
                        name="Groceries",
                        budget=Budget(amount=600.00, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)

            ledger_path = data_dir / "test.csv"
            write_ledger(
                ledger_path,
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id="test1",
                            date="2025-10-05",
                            description="SAMPLE STORE",
                            amount=-250.00,
                            currency="CAD",
                            account_id="MYBANK_CHQ",
                            category="Groceries",
                        ),
                    ),
                ],
            )

            build_projections_from_csvs(data_dir, workspace.projections_path)

            with patch("gilt.cli.command.report._check_pandoc", return_value=False):
                result = run(
                    year=2025,
                    month=10,
                    output=tmp / "reports" / "test_report",
                    workspace=workspace,
                    write=True,
                )

            assert result == 0

            md_path = tmp / "reports" / "test_report.md"
            assert md_path.exists()

            content = md_path.read_text(encoding="utf-8")
            assert "# Budget Report - 2025-10" in content
            assert "Groceries" in content
            assert "$600.00" in content
            assert "$250.00" in content

    def it_should_error_when_month_without_year(self):
        """Should return error when month is specified without year."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_dir = tmp / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = tmp / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=tmp)

            config = CategoryConfig(categories=[])
            save_categories_config(config_path, config)

            result = run(
                year=None,
                month=10,
                workspace=workspace,
                write=False,
            )

            assert result == 1

    def it_should_error_on_invalid_month(self):
        """Should return error when month is out of range."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_dir = tmp / "config"
            config_dir.mkdir()
            config_path = config_dir / "categories.yml"
            data_dir = tmp / "data" / "accounts"
            data_dir.mkdir(parents=True)
            workspace = Workspace(root=tmp)

            config = CategoryConfig(categories=[])
            save_categories_config(config_path, config)

            result = run(
                year=2025,
                month=13,
                workspace=workspace,
                write=False,
            )

            assert result == 1
