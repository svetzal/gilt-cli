from __future__ import annotations

"""Specs for the reporting command registration layer."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gilt.cli.app import app


class DescribeStatus:
    def it_should_exit_1_when_fy_is_unparseable(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.util.fy.fiscal_year_range",
                side_effect=ValueError("bad fy"),
            ),
            patch("gilt.cli.command.status.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["status", "--fy", "INVALID"])

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
            patch("gilt.cli.command.status.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["status", "--fy", "FY25"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["fy_range"] == fy_range
        assert call_kwargs["fy_label"] == "FY25"


class DescribeSummary:
    def it_should_exit_1_when_fy_and_year_both_given(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.summary.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["summary", "--fy", "FY25", "--year", "2025"])

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
            patch("gilt.cli.command.summary.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["summary", "--fy", "INVALID"])

        assert result.exit_code == 1
        mock_run.assert_not_called()

    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()
        fy_range = (MagicMock(), MagicMock())

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.util.fy.fiscal_year_range",
                return_value=fy_range,
            ),
            patch("gilt.cli.command.summary.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["summary", "--fy", "FY25"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["fy_range"] == fy_range
        assert call_kwargs["fy_label"] == "FY25"
        assert call_kwargs["workspace"] is ws


class DescribeYtd:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.ytd.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["ytd", "--account", "MYBANK_CHQ"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["account"] == "MYBANK_CHQ"
        assert call_kwargs["workspace"] is ws


class DescribeBudget:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.budget.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["budget", "--year", "2025"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["year"] == 2025
        assert call_kwargs["workspace"] is ws


class DescribeReport:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.report.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["report", "--year", "2025"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["year"] == 2025
        assert call_kwargs["write"] is False
        assert call_kwargs["workspace"] is ws


class DescribeShow:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.show.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["show", "--txid", "abc12345"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(txid="abc12345", workspace=ws)


class DescribeHistory:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.history.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["history", "EXAMPLE UTILITY"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["pattern"] == "EXAMPLE UTILITY"
        assert call_kwargs["workspace"] is ws
