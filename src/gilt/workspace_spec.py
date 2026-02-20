from __future__ import annotations

from pathlib import Path

from gilt.workspace import Workspace


class DescribeWorkspace:
    class DescribeResolve:
        def it_should_use_explicit_path_when_provided(self):
            ws = Workspace.resolve(explicit=Path("/tmp/my-finances"))
            assert ws.root == Path("/tmp/my-finances")

        def it_should_use_gilt_data_env_var_when_set(self, monkeypatch):
            monkeypatch.setenv("GILT_DATA", "/tmp/env-finances")
            ws = Workspace.resolve()
            assert ws.root == Path("/tmp/env-finances")

        def it_should_prefer_explicit_over_env_var(self, monkeypatch):
            monkeypatch.setenv("GILT_DATA", "/tmp/env-finances")
            ws = Workspace.resolve(explicit=Path("/tmp/explicit"))
            assert ws.root == Path("/tmp/explicit")

        def it_should_fall_back_to_cwd_when_no_env_var(self, monkeypatch):
            monkeypatch.delenv("GILT_DATA", raising=False)
            ws = Workspace.resolve()
            assert ws.root == Path.cwd()

    class DescribePaths:
        def it_should_compute_ledger_data_dir(self):
            ws = Workspace(root=Path("/data"))
            assert ws.ledger_data_dir == Path("/data/data/accounts")

        def it_should_compute_ingest_dir(self):
            ws = Workspace(root=Path("/data"))
            assert ws.ingest_dir == Path("/data/ingest")

        def it_should_compute_accounts_config(self):
            ws = Workspace(root=Path("/data"))
            assert ws.accounts_config == Path("/data/config/accounts.yml")

        def it_should_compute_categories_config(self):
            ws = Workspace(root=Path("/data"))
            assert ws.categories_config == Path("/data/config/categories.yml")
