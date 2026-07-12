"""Specs for gilt.ingest.config_loader — YAML config I/O."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from gilt.ingest.config_loader import load_accounts_config
from gilt.model.errors import ConfigLoadError


def _write_yaml(tmp_path: Path, content: str, filename: str = "accounts.yml") -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return p


class DescribeLoadAccountsConfig:
    def it_should_return_empty_list_for_missing_file(self, tmp_path):
        missing = tmp_path / "accounts.yml"
        result = load_accounts_config(missing)
        assert result == []

    def it_should_parse_minimal_account_entry(self, tmp_path):
        yml = _write_yaml(tmp_path, """\
            accounts:
              - account_id: MYBANK_CHQ
        """)
        result = load_accounts_config(yml)
        assert len(result) == 1
        assert result[0].account_id == "MYBANK_CHQ"

    def it_should_parse_source_patterns(self, tmp_path):
        yml = _write_yaml(tmp_path, """\
            accounts:
              - account_id: MYBANK_CHQ
                source_patterns:
                  - "mybank-chequing*.csv"
        """)
        result = load_accounts_config(yml)
        assert result[0].source_patterns == ["mybank-chequing*.csv"]

    def it_should_parse_multiple_accounts(self, tmp_path):
        yml = _write_yaml(tmp_path, """\
            accounts:
              - account_id: MYBANK_CHQ
              - account_id: BANK2_BIZ
        """)
        result = load_accounts_config(yml)
        assert len(result) == 2
        ids = {a.account_id for a in result}
        assert ids == {"MYBANK_CHQ", "BANK2_BIZ"}

    def it_should_return_empty_list_for_empty_yaml(self, tmp_path):
        yml = _write_yaml(tmp_path, "")
        result = load_accounts_config(yml)
        assert result == []

    def it_should_return_empty_list_for_yaml_with_no_accounts_key(self, tmp_path):
        yml = _write_yaml(tmp_path, "other_key: value")
        result = load_accounts_config(yml)
        assert result == []

    def it_should_parse_institution_and_product_fields(self, tmp_path):
        yml = _write_yaml(tmp_path, """\
            accounts:
              - account_id: MYBANK_CHQ
                institution: MyBank
                product: Chequing
                currency: CAD
        """)
        result = load_accounts_config(yml)
        assert result[0].institution == "MyBank"
        assert result[0].product == "Chequing"
        assert result[0].currency == "CAD"

    def it_should_raise_for_invalid_yaml(self, tmp_path):
        yml = _write_yaml(tmp_path, "invalid: yaml: content: [[[")

        with pytest.raises(ConfigLoadError) as exc_info:
            load_accounts_config(yml)
        assert str(yml) in str(exc_info.value)

    def it_should_raise_for_invalid_account_entry(self, tmp_path):
        yml = _write_yaml(tmp_path, """\
            accounts:
              - account_id: MYBANK_CHQ
                nature: not_a_valid_nature_value
        """)

        with pytest.raises(ConfigLoadError) as exc_info:
            load_accounts_config(yml)
        assert str(yml) in str(exc_info.value)
