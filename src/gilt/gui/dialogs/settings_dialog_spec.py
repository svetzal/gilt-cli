from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

import pytest

try:
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from gilt.gui.dialogs.settings_dialog import SettingsDialog

    HAS_QT = True
except ImportError:
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


class DescribeSettingsDialog:
    class DescribeGetDataDir:
        def it_should_use_gilt_data_env_var_when_set(self, monkeypatch):
            monkeypatch.setenv("GILT_DATA", "/tmp/finances")
            assert SettingsDialog.get_data_dir() == Path("/tmp/finances/data/accounts")

        def it_should_fall_back_to_qsettings(self, monkeypatch):
            monkeypatch.delenv("GILT_DATA", raising=False)
            with patch("gilt.gui.dialogs.settings_dialog.QSettings") as mock_qs:
                mock_qs.return_value.value.return_value = "/custom/data"
                assert SettingsDialog.get_data_dir() == Path("/custom/data")

        def it_should_fall_back_to_relative_default(self, monkeypatch):
            monkeypatch.delenv("GILT_DATA", raising=False)
            with patch("gilt.gui.dialogs.settings_dialog.QSettings") as mock_qs:
                mock_qs.return_value.value.side_effect = lambda key, default: default
                assert SettingsDialog.get_data_dir() == Path("data/accounts")

    class DescribeGetIngestDir:
        def it_should_use_gilt_data_env_var_when_set(self, monkeypatch):
            monkeypatch.setenv("GILT_DATA", "/tmp/finances")
            assert SettingsDialog.get_ingest_dir() == Path("/tmp/finances/ingest")

        def it_should_fall_back_to_relative_default(self, monkeypatch):
            monkeypatch.delenv("GILT_DATA", raising=False)
            with patch("gilt.gui.dialogs.settings_dialog.QSettings") as mock_qs:
                mock_qs.return_value.value.side_effect = lambda key, default: default
                assert SettingsDialog.get_ingest_dir() == Path("ingest")

    class DescribeGetAccountsConfig:
        def it_should_use_gilt_data_env_var_when_set(self, monkeypatch):
            monkeypatch.setenv("GILT_DATA", "/tmp/finances")
            assert SettingsDialog.get_accounts_config() == Path("/tmp/finances/config/accounts.yml")

        def it_should_fall_back_to_relative_default(self, monkeypatch):
            monkeypatch.delenv("GILT_DATA", raising=False)
            with patch("gilt.gui.dialogs.settings_dialog.QSettings") as mock_qs:
                mock_qs.return_value.value.side_effect = lambda key, default: default
                assert SettingsDialog.get_accounts_config() == Path("config/accounts.yml")

    class DescribeGetCategoriesConfig:
        def it_should_use_gilt_data_env_var_when_set(self, monkeypatch):
            monkeypatch.setenv("GILT_DATA", "/tmp/finances")
            assert SettingsDialog.get_categories_config() == Path(
                "/tmp/finances/config/categories.yml"
            )

        def it_should_fall_back_to_relative_default(self, monkeypatch):
            monkeypatch.delenv("GILT_DATA", raising=False)
            with patch("gilt.gui.dialogs.settings_dialog.QSettings") as mock_qs:
                mock_qs.return_value.value.side_effect = lambda key, default: default
                assert SettingsDialog.get_categories_config() == Path("config/categories.yml")
