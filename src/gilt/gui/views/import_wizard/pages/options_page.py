from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QGroupBox,
    QLabel,
    QVBoxLayout,
    QWizardPage,
)


class OptionsPage(QWizardPage):
    """Step 4: Import options."""

    def __init__(self):
        super().__init__()

        self.setTitle("Import Options")
        self.setSubTitle("Configure how the import should be performed.")

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        group = QGroupBox("Import Settings")
        group_layout = QVBoxLayout(group)

        self.write_check = QCheckBox("Write changes to ledger files (uncheck for dry-run)")
        self.write_check.setChecked(False)
        group_layout.addWidget(self.write_check)

        dry_run_info = QLabel(
            "If unchecked, the import will run in simulation mode. No files will be modified."
        )
        dry_run_info.setWordWrap(True)
        dry_run_info.setStyleSheet("color: palette(placeholder-text); padding-left: 20px;")
        group_layout.addWidget(dry_run_info)

        group_layout.addSpacing(10)

        duplicate_info = QLabel(
            "ℹ <b>Duplicate Detection:</b> Transactions are automatically deduplicated "
            "based on their transaction ID (hash of account, date, amount, and description). "
            "Existing transactions will not be re-imported."
        )
        duplicate_info.setWordWrap(True)
        duplicate_info.setStyleSheet(
            "background-color: rgba(209, 236, 241, 0.2); "
            "color: palette(text); "
            "padding: 8px; "
            "border-radius: 4px; "
            "border: 1px solid palette(mid);"
        )
        group_layout.addWidget(duplicate_info)

        layout.addWidget(group)
        layout.addStretch()

    def get_write_enabled(self) -> bool:
        return self.write_check.isChecked()
