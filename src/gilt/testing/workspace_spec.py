from __future__ import annotations

from gilt.model.category import Category, CategoryConfig
from gilt.testing.fixtures import make_group
from gilt.testing.workspace import build_workspace_with_ledger


class DescribeBuildWorkspaceWithLedger:
    def it_should_create_empty_workspace(self, tmp_path):
        ws = build_workspace_with_ledger(tmp_path)
        assert ws.categories_config.exists()
        assert ws.ledger_data_dir.exists()

    def it_should_use_provided_config(self, tmp_path):
        config = CategoryConfig(categories=[Category(name="Custom")])
        ws = build_workspace_with_ledger(tmp_path, config=config)
        from gilt.model.category_io import load_categories_config

        loaded = load_categories_config(ws.categories_config)
        assert loaded.categories[0].name == "Custom"

    def it_should_write_groups_as_ledger(self, tmp_path):
        groups = [make_group(account_id="TEST")]
        ws = build_workspace_with_ledger(tmp_path, groups=groups)
        assert (ws.ledger_data_dir / "TEST.csv").exists()

    def it_should_build_projections_when_requested(self, tmp_path):
        groups = [make_group(account_id="MYBANK_CHQ")]
        ws = build_workspace_with_ledger(tmp_path, groups=groups, projections=True)
        assert ws.projections_path.exists()
