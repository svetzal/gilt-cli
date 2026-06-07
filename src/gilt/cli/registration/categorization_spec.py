from __future__ import annotations

"""Specs for the categorization command registration layer."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gilt.cli.app import app


class DescribeUncategorized:
    def it_should_exit_1_when_fy_and_year_both_given(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.uncategorized.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["uncategorized", "--fy", "FY25", "--year", "2025"])

        assert result.exit_code == 1
        assert "cannot be used together" in result.output
        mock_run.assert_not_called()

    def it_should_exit_1_when_fy_is_unparseable(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.util.fy.fiscal_year_range",
                side_effect=ValueError("bad fy"),
            ),
            patch("gilt.cli.command.uncategorized.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["uncategorized", "--fy", "INVALID"])

        assert result.exit_code == 1
        mock_run.assert_not_called()

    def it_should_pass_fy_range_and_label_to_run(self):
        runner = CliRunner()
        ws = MagicMock()
        fy_range = (MagicMock(), MagicMock())

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.util.fy.fiscal_year_range",
                return_value=fy_range,
            ),
            patch("gilt.cli.command.uncategorized.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["uncategorized", "--fy", "FY25"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["fy_range"] == fy_range
        assert call_kwargs["fy_label"] == "FY25"


class DescribeRecategorize:
    def it_should_exit_1_when_build_date_selection_returns_error(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.cli.command.recategorize.build_date_selection",
                return_value="date parse error",
            ),
            patch("gilt.cli.command.recategorize.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                app, ["recategorize", "--to", "Work", "--date-from", "not-a-date"]
            )

        assert result.exit_code == 1
        assert "date parse error" in result.output
        mock_run.assert_not_called()

    def it_should_delegate_recategorize_to_run(self):
        runner = CliRunner()
        ws = MagicMock()
        date_from = MagicMock()
        date_to = MagicMock()
        fy_range = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.cli.command.recategorize.build_date_selection",
                return_value=(date_from, date_to, fy_range),
            ),
            patch("gilt.cli.command.recategorize.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["recategorize", "--from", "Business", "--to", "Work"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["date_from"] == date_from
        assert call_kwargs["date_to"] == date_to
        assert call_kwargs["fy_range"] == fy_range


class DescribeCategorize:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.categorize.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                app,
                [
                    "categorize",
                    "--account",
                    "MYBANK_CHQ",
                    "--txid",
                    "abc12345",
                    "--category",
                    "Housing",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["account"] == "MYBANK_CHQ"
        assert call_kwargs["write"] is False


class DescribeAutoCategorize:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.auto_categorize.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["auto-categorize"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["write"] is False
        assert call_kwargs["workspace"] is ws


class DescribeDiagnoseCategories:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.diagnose_categories.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["diagnose-categories"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(workspace=ws)


class DescribeInferRules:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.infer_rules.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["infer-rules"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["workspace"] is ws
        assert call_kwargs["write"] is False
