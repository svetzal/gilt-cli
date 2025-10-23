from __future__ import annotations

"""
Tests for report command.
"""

from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from finance.cli.command.report import run, _generate_markdown_report, _aggregate_spending
from finance.model.category import Budget, BudgetPeriod, Category, CategoryConfig, Subcategory
from finance.model.category_io import save_categories_config
from finance.model.account import Transaction, TransactionGroup
from finance.model.ledger_io import dump_ledger_csv


def _write_ledger(path: Path, groups: list[TransactionGroup]):
    """Helper to write a ledger file."""
    text = dump_ledger_csv(groups)
    path.write_text(text, encoding="utf-8")


class DescribeReportCommand:
    """Tests for the report command."""

    def it_should_generate_markdown_in_dry_run(self):
        """Should display dry-run message and preview without writing files."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_path = tmp / "categories.yml"
            data_dir = tmp / "data"
            data_dir.mkdir()

            # Create config with budget
            config = CategoryConfig(
                categories=[
                    Category(
                        name="Housing",
                        budget=Budget(amount=2500.00, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)

            # Create ledger with spending
            ledger_path = data_dir / "test.csv"
            _write_ledger(
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
                            account_id="TEST",
                            category="Housing",
                        )
                    ),
                ],
            )

            # Run in dry-run mode (write=False)
            result = run(
                year=2025,
                month=10,
                output=tmp / "reports" / "test_report",
                config=config_path,
                data_dir=data_dir,
                write=False,
            )

            # Should succeed
            assert result == 0

            # Should not create files
            assert not (tmp / "reports" / "test_report.md").exists()
            assert not (tmp / "reports" / "test_report.docx").exists()

    def it_should_write_markdown_file_with_write_flag(self):
        """Should write markdown file when --write is specified."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_path = tmp / "categories.yml"
            data_dir = tmp / "data"
            data_dir.mkdir()

            # Create config with budget
            config = CategoryConfig(
                categories=[
                    Category(
                        name="Groceries",
                        budget=Budget(amount=600.00, period=BudgetPeriod.monthly),
                    ),
                ]
            )
            save_categories_config(config_path, config)

            # Create ledger with spending
            ledger_path = data_dir / "test.csv"
            _write_ledger(
                ledger_path,
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id="test1",
                            date="2025-10-05",
                            description="Grocery Store",
                            amount=-250.00,
                            currency="CAD",
                            account_id="TEST",
                            category="Groceries",
                        )
                    ),
                ],
            )

            # Mock pandoc check to avoid requirement
            with patch("finance.cli.command.report._check_pandoc", return_value=False):
                # Run with write=True
                result = run(
                    year=2025,
                    month=10,
                    output=tmp / "reports" / "test_report",
                    config=config_path,
                    data_dir=data_dir,
                    write=True,
                )

            # Should succeed
            assert result == 0

            # Should create markdown file
            md_path = tmp / "reports" / "test_report.md"
            assert md_path.exists()

            # Verify content
            content = md_path.read_text(encoding="utf-8")
            assert "# Budget Report - 2025-10" in content
            assert "Groceries" in content
            assert "$600.00" in content  # Budget
            assert "$250.00" in content  # Actual

    def it_should_error_when_month_without_year(self):
        """Should return error when month is specified without year."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_path = tmp / "categories.yml"
            data_dir = tmp / "data"
            data_dir.mkdir()

            # Create minimal config
            config = CategoryConfig(categories=[])
            save_categories_config(config_path, config)

            # Run with month but no year
            result = run(
                year=None,
                month=10,
                config=config_path,
                data_dir=data_dir,
                write=False,
            )

            # Should fail
            assert result == 1

    def it_should_error_on_invalid_month(self):
        """Should return error when month is out of range."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            config_path = tmp / "categories.yml"
            data_dir = tmp / "data"
            data_dir.mkdir()

            # Create minimal config
            config = CategoryConfig(categories=[])
            save_categories_config(config_path, config)

            # Run with invalid month
            result = run(
                year=2025,
                month=13,
                config=config_path,
                data_dir=data_dir,
                write=False,
            )

            # Should fail
            assert result == 1


class DescribeMarkdownGeneration:
    """Tests for markdown report generation."""

    def it_should_generate_summary_table(self):
        """Should generate a summary table with budget vs actual."""
        config = CategoryConfig(
            categories=[
                Category(
                    name="Dining Out",
                    budget=Budget(amount=400.00, period=BudgetPeriod.monthly),
                ),
                Category(
                    name="Entertainment",
                    budget=Budget(amount=200.00, period=BudgetPeriod.monthly),
                ),
            ]
        )

        spending = {
            ("Dining Out", None): 350.00,
            ("Entertainment", None): 150.00,
        }

        markdown = _generate_markdown_report(config, spending, {}, 2025, 10)

        # Check structure
        assert "# Budget Report - 2025-10" in markdown
        assert "## Budget Summary" in markdown
        assert "| Category | Budget | Actual | Remaining | % Used |" in markdown

        # Check data
        assert "Dining Out" in markdown
        assert "$400.00" in markdown
        assert "$350.00" in markdown

        assert "Entertainment" in markdown
        assert "$200.00" in markdown
        assert "$150.00" in markdown

    def it_should_include_detailed_breakdown(self):
        """Should include detailed breakdown by category."""
        config = CategoryConfig(
            categories=[
                Category(
                    name="Transportation",
                    description="Vehicle and transit expenses",
                    budget=Budget(amount=800.00, period=BudgetPeriod.monthly),
                    subcategories=[
                        Subcategory(name="Fuel"),
                        Subcategory(name="Transit"),
                    ],
                ),
            ]
        )

        spending = {
            ("Transportation", "Fuel"): 200.00,
            ("Transportation", "Transit"): 100.00,
        }

        transactions_by_category = {
            "Transportation": [
                ("2025-10-01", "Fuel Station", "Fuel", 200.00, "TEST"),
                ("2025-10-03", "City Transit", "Transit", 100.00, "TEST"),
            ]
        }

        markdown = _generate_markdown_report(config, spending, transactions_by_category, 2025, 10)

        # Check detailed section
        assert "## Detailed Breakdown" in markdown
        assert "### Transportation" in markdown
        assert "Vehicle and transit expenses" in markdown

        # Check transaction table for monthly report
        assert "| Date | Description | Subcategory | Amount | Account |" in markdown
        assert "Fuel Station" in markdown
        assert "$200.00" in markdown
        assert "City Transit" in markdown
        assert "$100.00" in markdown

    def it_should_show_over_budget_warning(self):
        """Should show warning for categories over budget."""
        config = CategoryConfig(
            categories=[
                Category(
                    name="Groceries",
                    budget=Budget(amount=500.00, period=BudgetPeriod.monthly),
                ),
            ]
        )

        spending = {
            ("Groceries", None): 650.00,  # Over budget
        }

        markdown = _generate_markdown_report(config, spending, {}, 2025, 10)

        # Check for over budget indicator
        assert "⚠️" in markdown
        assert "over budget" in markdown.lower()


class DescribeAggregateSpending:
    """Tests for spending aggregation."""

    def it_should_aggregate_by_category(self):
        """Should aggregate spending by category and subcategory."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            data_dir = tmp / "data"
            data_dir.mkdir()

            # Create ledger with multiple transactions
            ledger_path = data_dir / "test.csv"
            _write_ledger(
                ledger_path,
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id="test1",
                            date="2025-10-01",
                            description="Purchase 1",
                            amount=-100.00,
                            currency="CAD",
                            account_id="TEST",
                            category="Shopping",
                        )
                    ),
                    TransactionGroup(
                        group_id="2",
                        primary=Transaction(
                            transaction_id="test2",
                            date="2025-10-05",
                            description="Purchase 2",
                            amount=-150.00,
                            currency="CAD",
                            account_id="TEST",
                            category="Shopping",
                        )
                    ),
                ],
            )

            # Aggregate spending
            spending = _aggregate_spending(data_dir, 2025, 10)

            # Should sum amounts
            assert spending[("Shopping", None)] == 250.00

    def it_should_filter_by_year_and_month(self):
        """Should filter transactions by year and month."""
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            data_dir = tmp / "data"
            data_dir.mkdir()

            # Create ledger with transactions in different months
            ledger_path = data_dir / "test.csv"
            _write_ledger(
                ledger_path,
                [
                    TransactionGroup(
                        group_id="1",
                        primary=Transaction(
                            transaction_id="test1",
                            date="2025-10-01",
                            description="October",
                            amount=-100.00,
                            currency="CAD",
                            account_id="TEST",
                            category="Test",
                        )
                    ),
                    TransactionGroup(
                        group_id="2",
                        primary=Transaction(
                            transaction_id="test2",
                            date="2025-11-01",
                            description="November",
                            amount=-200.00,
                            currency="CAD",
                            account_id="TEST",
                            category="Test",
                        )
                    ),
                ],
            )

            # Aggregate for October only
            spending = _aggregate_spending(data_dir, 2025, 10)

            # Should only include October transaction
            assert spending[("Test", None)] == 100.00
