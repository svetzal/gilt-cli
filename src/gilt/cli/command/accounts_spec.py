from __future__ import annotations

"""
Specs for the accounts CLI command.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from pathlib import Path

from gilt.cli.command.accounts import _collect_accounts, run
from gilt.workspace import Workspace


def _write_accounts_config(config_path: Path, content: str) -> None:
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(content, encoding="utf-8")


def _make_workspace(tmp_path: Path) -> Workspace:
    ws = Workspace(root=tmp_path)
    ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
    return ws


class DescribeCollectAccounts:
    def it_should_return_empty_dict_when_no_config_and_no_ledgers(self, tmp_path):
        config_path = tmp_path / "config" / "accounts.yml"
        data_dir = tmp_path / "data" / "accounts"
        data_dir.mkdir(parents=True)

        result = _collect_accounts(config_path, data_dir)

        assert result == {}

    def it_should_include_accounts_from_config(self, tmp_path):
        config_path = tmp_path / "config" / "accounts.yml"
        _write_accounts_config(
            config_path,
            "accounts:\n"
            "  - account_id: MYBANK_CHQ\n"
            "    institution: MyBank\n"
            "    product: Chequing\n",
        )
        data_dir = tmp_path / "data" / "accounts"
        data_dir.mkdir(parents=True)

        result = _collect_accounts(config_path, data_dir)

        assert "MYBANK_CHQ" in result

    def it_should_include_unmanaged_ledger_files_not_in_config(self, tmp_path):
        config_path = tmp_path / "config" / "accounts.yml"
        data_dir = tmp_path / "data" / "accounts"
        data_dir.mkdir(parents=True)
        (data_dir / "MYBANK_CC.csv").write_text("", encoding="utf-8")

        result = _collect_accounts(config_path, data_dir)

        assert "MYBANK_CC" in result

    def it_should_handle_missing_data_directory(self, tmp_path):
        config_path = tmp_path / "config" / "accounts.yml"
        data_dir = tmp_path / "data" / "accounts"
        # data_dir intentionally not created

        result = _collect_accounts(config_path, data_dir)

        assert result == {}

    def it_should_prefer_config_description_over_id_alone(self, tmp_path):
        config_path = tmp_path / "config" / "accounts.yml"
        _write_accounts_config(
            config_path,
            "accounts:\n"
            "  - account_id: MYBANK_CHQ\n"
            "    institution: MyBank\n"
            "    product: Chequing\n",
        )
        data_dir = tmp_path / "data" / "accounts"
        data_dir.mkdir(parents=True)

        result = _collect_accounts(config_path, data_dir)

        assert result["MYBANK_CHQ"] != "MYBANK_CHQ"


class DescribeAccountsCommand:
    def it_should_return_zero_when_no_accounts_found(self, tmp_path):
        ws = _make_workspace(tmp_path)

        result = run(workspace=ws)

        assert result == 0

    def it_should_return_zero_when_accounts_are_found(self, tmp_path):
        ws = _make_workspace(tmp_path)
        _write_accounts_config(
            ws.accounts_config,
            "accounts:\n"
            "  - account_id: MYBANK_CHQ\n"
            "    institution: MyBank\n"
            "    product: Chequing\n",
        )

        result = run(workspace=ws)

        assert result == 0

    def it_should_return_zero_when_only_ledger_files_present(self, tmp_path):
        ws = _make_workspace(tmp_path)
        (ws.ledger_data_dir / "MYBANK_CC.csv").write_text("", encoding="utf-8")

        result = run(workspace=ws)

        assert result == 0
