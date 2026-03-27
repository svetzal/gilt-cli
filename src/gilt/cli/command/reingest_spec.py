from __future__ import annotations

"""
Specs for the reingest CLI command.

These tests verify command-level behavior (dry-run, account not found, no files).
The purge logic (collect/execute) is tested in reingestion_service_spec.py.
"""

from pathlib import Path

from gilt.cli.command.reingest import run
from gilt.workspace import Workspace


class DescribeReingestRunDryRun:
    """Specs for the reingest command run() in dry-run mode."""

    def it_should_return_one_when_account_not_in_config(self, tmp_path: Path):
        """Should return exit code 1 when the given account is not in config."""
        ws = Workspace(root=tmp_path)
        ws.accounts_config.parent.mkdir(parents=True, exist_ok=True)
        ws.accounts_config.write_text(
            "accounts: []\n",
            encoding="utf-8",
        )
        ws.ingest_dir.mkdir(parents=True, exist_ok=True)

        result = run(account="NONEXISTENT", workspace=ws, write=False)
        assert result == 1
