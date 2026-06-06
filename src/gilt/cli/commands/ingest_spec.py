from __future__ import annotations

"""Specs for the ingest command registration layer."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gilt.cli.app import app


class DescribeReceipts:
    def it_should_exit_1_when_fy_is_unparseable(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.util.fy.fiscal_year_range",
                side_effect=ValueError("bad fy"),
            ),
            patch("gilt.cli.command.receipts.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["receipts", "--fy", "INVALID"])

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
            patch("gilt.cli.command.receipts.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["receipts", "--fy", "FY25"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["fy_range"] == fy_range
        assert call_kwargs["fy_label"] == "FY25"


class DescribeIngestReceipts:
    def it_should_delegate_to_run_with_all_kwargs(self, tmp_path):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.ingest_receipts.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                app,
                [
                    "ingest-receipts",
                    "--source",
                    str(tmp_path),
                    "--year",
                    "2025",
                    "--account",
                    "MYBANK_CC",
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["year"] == 2025
        assert call_kwargs["account"] == "MYBANK_CC"
        assert call_kwargs["write"] is False
        assert call_kwargs["workspace"] is ws
