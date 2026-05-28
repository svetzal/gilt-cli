from __future__ import annotations

"""
Specs for the gilt CLI application entry point.

Tests cover: workspace context helper, callback workspace resolution,
and command registration surface.
"""

from unittest.mock import MagicMock, patch

from gilt.cli.app import _ws, app


class DescribeWs:
    def it_should_return_workspace_stored_in_context(self):
        ctx = MagicMock()
        ctx.obj = {"workspace": "sentinel_workspace"}
        assert _ws(ctx) == "sentinel_workspace"


class DescribeMainCallback:
    def it_should_store_resolved_workspace_in_context(self, tmp_path):
        from gilt.workspace import Workspace

        ws = Workspace(root=tmp_path)
        ctx = MagicMock()
        ctx.obj = {}

        with patch("gilt.cli.app.Workspace.resolve", return_value=ws):
            from gilt.cli.app import main

            main(ctx=ctx, data_dir=None)

        assert ctx.obj["workspace"] is ws


class DescribeWorkspaceResolution:
    """Specs for workspace resolution in the main callback."""

    def it_should_use_data_dir_when_provided(self, tmp_path):
        from gilt.workspace import Workspace

        ctx = MagicMock()
        ctx.obj = {}

        with patch(
            "gilt.cli.app.Workspace.resolve", return_value=Workspace(root=tmp_path)
        ) as mock_resolve:
            from gilt.cli.app import main

            main(ctx=ctx, data_dir=tmp_path)

        mock_resolve.assert_called_once_with(tmp_path)

    def it_should_fall_back_to_gilt_data_env_var(self):
        from gilt.workspace import Workspace

        ctx = MagicMock()
        ctx.obj = {}
        fake_ws = MagicMock(spec=Workspace)

        with patch("gilt.cli.app.Workspace.resolve", return_value=fake_ws) as mock_resolve:
            from gilt.cli.app import main

            main(ctx=ctx, data_dir=None)

        mock_resolve.assert_called_once_with(None)

    def it_should_default_to_current_directory(self):
        from gilt.workspace import Workspace

        ctx = MagicMock()
        ctx.obj = {}
        fake_ws = MagicMock(spec=Workspace)

        with patch("gilt.cli.app.Workspace.resolve", return_value=fake_ws) as mock_resolve:
            from gilt.cli.app import main

            main(ctx=ctx, data_dir=None)

        mock_resolve.assert_called_once()


class DescribeAppCommandRegistration:
    def it_should_register_ingest_command(self):
        names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "ingest" in names

    def it_should_register_categorize_command(self):
        names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "categorize" in names

    def it_should_register_ytd_command(self):
        names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "ytd" in names

    def it_should_register_budget_command(self):
        names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "budget" in names

    def it_should_register_note_command(self):
        names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "note" in names

    def it_should_register_init_command(self):
        names = [c.name or c.callback.__name__ for c in app.registered_commands]
        assert "init" in names

    def it_should_register_all_expected_commands(self):
        names = {c.name or c.callback.__name__ for c in app.registered_commands}
        expected = {
            "ingest",
            "reingest",
            "note",
            "ytd",
            "categorize",
            "recategorize",
            "auto-categorize",
            "uncategorized",
            "budget",
            "report",
            "duplicates",
            "mark-duplicate",
            "categories",
            "category",
            "accounts",
            "init",
            "diagnose_categories",
            "rebuild-projections",
            "backfill-events",
            "migrate-to-events",
            "audit-ml",
            "prompt-stats",
            "infer-rules",
            "skill-init",
            "ingest-receipts",
        }
        assert expected <= names


class DescribeCommandDelegation:
    """Specs verifying that Typer wrappers delegate to their run() functions."""

    def it_should_delegate_ingest_to_run(self, tmp_path):
        from typer.testing import CliRunner

        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.ingest.run", return_value=0) as mock_run,
        ):
            runner.invoke(app, ["ingest"])

        mock_run.assert_called_once_with(workspace=ws, write=False)

    def it_should_delegate_note_to_run_with_write_flag(self, tmp_path):
        from typer.testing import CliRunner

        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.note.run", return_value=0) as mock_run,
        ):
            runner.invoke(
                app,
                ["note", "--account", "MYBANK_CHQ", "--txid", "abc12345", "--note", "test note"],
            )

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args.kwargs
        assert call_kwargs["account"] == "MYBANK_CHQ"
        assert call_kwargs["write"] is False

    def it_should_delegate_reingest_to_run(self, tmp_path):
        from typer.testing import CliRunner

        runner = CliRunner()
        ws = MagicMock()

        with (
            patch("gilt.cli.app.Workspace.resolve", return_value=ws),
            patch("gilt.cli.command.reingest.run", return_value=0) as mock_run,
        ):
            runner.invoke(app, ["reingest", "--account", "MYBANK_CHQ"])

        mock_run.assert_called_once_with(account="MYBANK_CHQ", workspace=ws, write=False)
