from __future__ import annotations

"""
Settings Dialog - Configuration dialog for application settings

Allows users to configure data directories and other basic settings.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QFileDialog,
    QDialogButtonBox,
    QTabWidget,
    QWidget,
)
from PySide6.QtCore import QSettings


class SettingsDialog(QDialog):
    """Dialog for application settings."""

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setWindowTitle("Settings")
        self.setMinimumWidth(600)
        self.setModal(True)

        self.settings = QSettings()

        self._init_ui()
        self._load_settings()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Tab widget for different setting categories
        tabs = QTabWidget()
        tabs.addTab(self._create_general_tab(), "General")
        tabs.addTab(self._create_paths_tab(), "Paths")
        layout.addWidget(tabs)

        # Dialog buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _create_general_tab(self) -> QWidget:
        """Create the General settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Default currency
        self.currency_edit = QLineEdit()
        self.currency_edit.setPlaceholderText("CAD")
        self.currency_edit.setMaxLength(3)
        layout.addRow("Default Currency:", self.currency_edit)

        # Info label
        info = QLabel(
            "Default currency is used when importing transactions without currency information."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(placeholder-text); font-size: 10pt;")
        layout.addRow("", info)

        return widget

    def _create_paths_tab(self) -> QWidget:
        """Create the Paths settings tab."""
        widget = QWidget()
        layout = QFormLayout(widget)

        # Data directory
        self.data_dir_edit = QLineEdit()
        self.data_dir_edit.setReadOnly(True)
        data_dir_layout = QHBoxLayout()
        data_dir_layout.addWidget(self.data_dir_edit)
        browse_data_btn = QPushButton("Browse...")
        browse_data_btn.clicked.connect(self._browse_data_dir)
        data_dir_layout.addWidget(browse_data_btn)
        layout.addRow("Data Directory:", data_dir_layout)

        # Ingest directory
        self.ingest_dir_edit = QLineEdit()
        self.ingest_dir_edit.setReadOnly(True)
        ingest_dir_layout = QHBoxLayout()
        ingest_dir_layout.addWidget(self.ingest_dir_edit)
        browse_ingest_btn = QPushButton("Browse...")
        browse_ingest_btn.clicked.connect(self._browse_ingest_dir)
        ingest_dir_layout.addWidget(browse_ingest_btn)
        layout.addRow("Ingest Directory:", ingest_dir_layout)

        # Accounts config path
        self.accounts_config_edit = QLineEdit()
        self.accounts_config_edit.setReadOnly(True)
        accounts_config_layout = QHBoxLayout()
        accounts_config_layout.addWidget(self.accounts_config_edit)
        browse_accounts_btn = QPushButton("Browse...")
        browse_accounts_btn.clicked.connect(self._browse_accounts_config)
        accounts_config_layout.addWidget(browse_accounts_btn)
        layout.addRow("Accounts Config:", accounts_config_layout)

        # Categories config path
        self.categories_config_edit = QLineEdit()
        self.categories_config_edit.setReadOnly(True)
        categories_config_layout = QHBoxLayout()
        categories_config_layout.addWidget(self.categories_config_edit)
        browse_categories_btn = QPushButton("Browse...")
        browse_categories_btn.clicked.connect(self._browse_categories_config)
        categories_config_layout.addWidget(browse_categories_btn)
        layout.addRow("Categories Config:", categories_config_layout)

        # Info label
        info = QLabel(
            "These paths determine where the application looks for "
            "ledger files and configuration. Changes require restart."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(placeholder-text); font-size: 10pt;")
        layout.addRow("", info)

        return widget

    def _browse_data_dir(self):
        """Browse for data directory."""
        current = self.data_dir_edit.text() or str(Path.cwd() / "data/accounts")
        directory = QFileDialog.getExistingDirectory(self, "Select Data Directory", current)
        if directory:
            self.data_dir_edit.setText(directory)

    def _browse_ingest_dir(self):
        """Browse for ingest directory."""
        current = self.ingest_dir_edit.text() or str(Path.cwd() / "ingest")
        directory = QFileDialog.getExistingDirectory(self, "Select Ingest Directory", current)
        if directory:
            self.ingest_dir_edit.setText(directory)

    def _browse_accounts_config(self):
        """Browse for accounts config file."""
        current = self.accounts_config_edit.text() or str(Path.cwd() / "config/accounts.yml")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Accounts Config",
            str(Path(current).parent),
            "YAML Files (*.yml *.yaml);;All Files (*)",
        )
        if file_path:
            self.accounts_config_edit.setText(file_path)

    def _browse_categories_config(self):
        """Browse for categories config file."""
        current = self.categories_config_edit.text() or str(Path.cwd() / "config/categories.yml")
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Categories Config",
            str(Path(current).parent),
            "YAML Files (*.yml *.yaml);;All Files (*)",
        )
        if file_path:
            self.categories_config_edit.setText(file_path)

    def _load_settings(self):
        """Load settings from QSettings."""
        # General
        self.currency_edit.setText(self.settings.value("general/default_currency", "CAD"))

        # Paths
        self.data_dir_edit.setText(self.settings.value("paths/data_dir", "data/accounts"))
        self.ingest_dir_edit.setText(self.settings.value("paths/ingest_dir", "ingest"))
        self.accounts_config_edit.setText(
            self.settings.value("paths/accounts_config", "config/accounts.yml")
        )
        self.categories_config_edit.setText(
            self.settings.value("paths/categories_config", "config/categories.yml")
        )

    def accept(self):
        """Save settings and close dialog."""
        # General
        self.settings.setValue("general/default_currency", self.currency_edit.text() or "CAD")

        # Paths
        self.settings.setValue("paths/data_dir", self.data_dir_edit.text())
        self.settings.setValue("paths/ingest_dir", self.ingest_dir_edit.text())
        self.settings.setValue("paths/accounts_config", self.accounts_config_edit.text())
        self.settings.setValue("paths/categories_config", self.categories_config_edit.text())

        super().accept()

    @staticmethod
    def get_data_dir() -> Path:
        """Get the configured data directory."""
        settings = QSettings()
        return Path(settings.value("paths/data_dir", "data/accounts"))

    @staticmethod
    def get_ingest_dir() -> Path:
        """Get the configured ingest directory."""
        settings = QSettings()
        return Path(settings.value("paths/ingest_dir", "ingest"))

    @staticmethod
    def get_accounts_config() -> Path:
        """Get the configured accounts config path."""
        settings = QSettings()
        return Path(settings.value("paths/accounts_config", "config/accounts.yml"))

    @staticmethod
    def get_categories_config() -> Path:
        """Get the configured categories config path."""
        settings = QSettings()
        return Path(settings.value("paths/categories_config", "config/categories.yml"))

    @staticmethod
    def get_default_currency() -> str:
        """Get the configured default currency."""
        settings = QSettings()
        return settings.value("general/default_currency", "CAD")
