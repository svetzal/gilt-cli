from __future__ import annotations

import sqlite3

from gilt.cli.command.util import require_projections
from gilt.workspace import Workspace


class DescribeRequireProjections:
    def it_should_return_projection_builder_when_db_exists(self, tmp_path):
        projections_path = tmp_path / "data" / "projections.db"
        projections_path.parent.mkdir(parents=True)
        sqlite3.connect(projections_path).close()
        workspace = Workspace(root=tmp_path)

        result = require_projections(workspace)

        assert result is not None

    def it_should_return_none_when_db_is_missing(self, tmp_path, capsys):
        workspace = Workspace(root=tmp_path)

        result = require_projections(workspace)

        assert result is None

    def it_should_print_error_message_when_db_is_missing(self, tmp_path, capsys):
        workspace = Workspace(root=tmp_path)

        require_projections(workspace)

        # Rich console writes to stdout; capture it
        captured = capsys.readouterr()
        assert "rebuild-projections" in captured.out
