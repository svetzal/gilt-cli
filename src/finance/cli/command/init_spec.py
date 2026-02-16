"""Tests for init command."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from finance.cli.command.init import run
from finance.workspace import Workspace


class DescribeInitCommand:
    """Tests for init command."""

    def it_should_create_all_directories_and_config_files(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            rc = run(workspace=workspace)

            assert rc == 0
            assert workspace.ledger_data_dir.is_dir()
            assert workspace.ingest_dir.is_dir()
            assert workspace.reports_dir.is_dir()
            assert (Path(tmpdir) / "config").is_dir()
            assert workspace.accounts_config.is_file()
            assert workspace.categories_config.is_file()

    def it_should_be_safe_to_run_twice(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            rc1 = run(workspace=workspace)
            assert rc1 == 0

            # Write something to a config file to verify it's not overwritten
            workspace.accounts_config.write_text("custom content", encoding="utf-8")

            rc2 = run(workspace=workspace)
            assert rc2 == 0

            # Config file should not be overwritten
            assert workspace.accounts_config.read_text(encoding="utf-8") == "custom content"

    def it_should_skip_existing_directories(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            # Pre-create one directory
            workspace.ledger_data_dir.mkdir(parents=True)

            rc = run(workspace=workspace)
            assert rc == 0

            # Everything else should still be created
            assert workspace.ingest_dir.is_dir()
            assert workspace.reports_dir.is_dir()
            assert workspace.categories_config.is_file()

    def it_should_create_valid_starter_categories_config(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            run(workspace=workspace)

            from finance.model.category_io import load_categories_config
            config = load_categories_config(workspace.categories_config)
            assert config.categories == []

    def it_should_create_parseable_accounts_config(self):
        with TemporaryDirectory() as tmpdir:
            workspace = Workspace(root=Path(tmpdir))
            run(workspace=workspace)

            import yaml
            data = yaml.safe_load(workspace.accounts_config.read_text(encoding="utf-8"))
            assert data["accounts"] == []
