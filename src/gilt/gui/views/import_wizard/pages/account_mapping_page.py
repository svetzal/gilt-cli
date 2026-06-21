from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWizardPage,
)

from gilt.gui.services.import_service import ImportFileMapping, ImportService
from gilt.gui.views.import_wizard._page_ids import PAGE_SELECT_FILES
from gilt.gui.views.import_wizard.pages.file_selection_page import FileSelectionPage


class AccountMappingPage(QWizardPage):
    """Step 2: Map files to accounts."""

    def __init__(self, service: ImportService):
        super().__init__()
        self.service = service

        self.setTitle("Account Mapping")
        self.setSubTitle("Review and confirm which account each file should be imported to.")

        self.mappings: list[ImportFileMapping] = []

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["File", "Detected Account", "Import To", "Status"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        header.resizeSection(0, 250)
        header.resizeSection(1, 150)
        header.resizeSection(2, 150)
        header.resizeSection(3, 100)

        layout.addWidget(self.table)

        info = QLabel(
            "<i>Auto-detected accounts are shown. You can change the target account "
            "using the dropdown in the 'Import To' column.</i>"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(placeholder-text); padding: 8px;")
        layout.addWidget(info)

    def initializePage(self):
        wizard = self.wizard()
        if not hasattr(wizard, "service"):
            return

        file_selection_page = wizard.page(PAGE_SELECT_FILES)
        if not isinstance(file_selection_page, FileSelectionPage):
            return

        selected_files = file_selection_page.get_selected_files()

        self.mappings = []
        self.table.setRowCount(0)

        accounts = self.service.load_accounts()
        account_ids = [acc.account_id for acc in accounts]

        for file_path in selected_files:
            mapping = self.service.build_file_mapping(file_path, max_preview_rows=3)
            self.mappings.append(mapping)

            row = self.table.rowCount()
            self.table.insertRow(row)

            self.table.setItem(row, 0, QTableWidgetItem(mapping.file_info.name))

            detected = (
                mapping.detected_account.account_id if mapping.detected_account else "Unknown"
            )
            self.table.setItem(row, 1, QTableWidgetItem(detected))

            combo = QComboBox()
            combo.addItems(account_ids)
            if mapping.selected_account_id:
                index = combo.findText(mapping.selected_account_id)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.currentTextChanged.connect(lambda text, r=row: self._on_account_changed(r, text))
            self.table.setCellWidget(row, 2, combo)

            status = "✓ Ready" if mapping.selected_account_id else "⚠ Unknown"
            status_item = QTableWidgetItem(status)
            if not mapping.selected_account_id:
                status_item.setForeground(Qt.red)
            self.table.setItem(row, 3, status_item)

    def _on_account_changed(self, row: int, account_id: str):
        if row < len(self.mappings):
            self.mappings[row].selected_account_id = account_id

            status_item = self.table.item(row, 3)
            if status_item:
                status_item.setText("✓ Ready")
                status_item.setForeground(Qt.black)

        self.completeChanged.emit()

    def isComplete(self) -> bool:
        return all(m.selected_account_id for m in self.mappings)

    def get_mappings(self) -> list[ImportFileMapping]:
        return self.mappings
