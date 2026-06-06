from __future__ import annotations

"""Specs for the setup command registration layer."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gilt.cli.app import app


class DescribeSkillInit:
    def it_should_delegate_to_run_with_defaults(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.skill_init.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["skill-init"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["global_install"] is False
        assert call_kwargs["force"] is False
        assert call_kwargs["json_output"] is False

    def it_should_forward_global_flag(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.skill_init.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["skill-init", "--global"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["global_install"] is True

    def it_should_forward_force_flag(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.skill_init.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["skill-init", "--force"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["force"] is True


class DescribeInit:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.init.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["init"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(workspace=ws)


class DescribeAccounts:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.accounts.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["accounts"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(workspace=ws)


class DescribeCategories:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.categories.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["categories"])

        assert result.exit_code == 0
        mock_run.assert_called_once_with(workspace=ws)


class DescribeCategory:
    def it_should_delegate_to_run_with_all_kwargs(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.category.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(
                app,
                ["category", "--add", "Housing:Utilities", "--write"],
            )

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["add"] == "Housing:Utilities"
        assert call_kwargs["write"] is True
        assert call_kwargs["workspace"] is ws
