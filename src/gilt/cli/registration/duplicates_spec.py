from __future__ import annotations

"""Specs for the duplicates command registration layer."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gilt.cli.app import app
from gilt.config import DEFAULT_OLLAMA_MODEL


class DescribeDuplicates:
    def it_should_default_model_to_default_ollama_model(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.duplicates.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["duplicates"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["model"] == DEFAULT_OLLAMA_MODEL

    def it_should_map_llm_flag_to_use_llm(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.duplicates.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["duplicates", "--llm"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["use_llm"] is True

    def it_should_map_interactive_flag(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.duplicates.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["duplicates", "-i"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["interactive"] is True


class DescribeMarkDuplicate:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.mark_duplicate.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                app,
                ["mark-duplicate", "--primary", "abc12345", "--duplicate", "def67890"],
            )

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["primary_txid"] == "abc12345"
        assert call_kwargs["duplicate_txid"] == "def67890"
        assert call_kwargs["write"] is False
        assert call_kwargs["workspace"] is ws


class DescribeDiagnoseDuplicates:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.diagnose_duplicates.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["diagnose-duplicates"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(workspace=ws)


class DescribeAuditMl:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.audit_ml.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["audit-ml", "--mode", "training"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["mode"] == "training"
        assert call_kwargs["workspace"] is ws


class DescribePromptStats:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.prompt_stats.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["prompt-stats"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["workspace"] is ws
        assert call_kwargs["generate_update"] is False
