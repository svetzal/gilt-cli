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
