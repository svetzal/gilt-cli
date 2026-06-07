from __future__ import annotations

"""Specs for the events command registration layer."""

from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

from gilt.cli.app import app


class DescribeBackfillEvents:
    def it_should_pass_dry_run_true_when_write_omitted(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.backfill_events.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["backfill-events"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["dry_run"] is True

    def it_should_pass_dry_run_false_when_write_given(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.backfill_events.run", return_value=0) as mock_run,
        ):
            result = runner.invoke(app, ["backfill-events", "--write"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["dry_run"] is False


class DescribeRebuildProjections:
    def it_should_delegate_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.cli.command.rebuild_projections.run", return_value=0
            ) as mock_run,
        ):
            result = runner.invoke(app, ["rebuild-projections", "--from-scratch"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["from_scratch"] is True
        assert call_kwargs["workspace"] is ws

    def it_should_forward_db_path_overrides(self, tmp_path):
        runner = CliRunner()
        ws = MagicMock()
        events_db = tmp_path / "events.db"
        projections_db = tmp_path / "projections.db"

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.cli.command.rebuild_projections.run", return_value=0
            ) as mock_run,
        ):
            result = runner.invoke(
                app,
                [
                    "rebuild-projections",
                    "--events-db",
                    str(events_db),
                    "--projections-db",
                    str(projections_db),
                ],
            )

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["events_db"] == events_db
        assert call_kwargs["projections_db"] == projections_db


class DescribeMigrateToEvents:
    def it_should_delegate_write_and_force_to_run(self):
        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch(
                "gilt.cli.command.migrate_to_events.run", return_value=0
            ) as mock_run,
        ):
            result = runner.invoke(app, ["migrate-to-events", "--write", "--force"])

        assert result.exit_code == 0
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["write"] is True
        assert call_kwargs["force"] is True
        assert call_kwargs["workspace"] is ws
