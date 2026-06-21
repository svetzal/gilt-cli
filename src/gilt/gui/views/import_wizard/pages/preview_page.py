from __future__ import annotations

from PySide6.QtWidgets import (
    QHeaderView,
    QLabel,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWizardPage,
)

from gilt.gui.services.import_service import ImportFileMapping, ImportService
from gilt.gui.views.import_wizard._page_ids import PAGE_ACCOUNT_MAPPING
from gilt.gui.views.import_wizard.pages.account_mapping_page import AccountMappingPage


class PreviewPage(QWizardPage):
    """Step 3: Preview transactions."""

    def __init__(self, service: ImportService):
        super().__init__()
        self.service = service

        self.setTitle("Preview & Verify")
        self.setSubTitle("Review the files and preview data before importing.")

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        layout.addWidget(self.table)

        warning = QLabel(
            "⚠ <b>Note:</b> This is a preview of the raw CSV data. "
            "The actual import will normalize column names and detect duplicates."
        )
        warning.setWordWrap(True)
        warning.setStyleSheet(
            "background-color: rgba(255, 243, 205, 0.2); "
            "color: palette(text); "
            "padding: 8px; "
            "border-radius: 4px; "
            "border: 1px solid palette(mid);"
        )
        layout.addWidget(warning)

    def initializePage(self):
        wizard = self.wizard()
        if not hasattr(wizard, "service"):
            return

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        if not isinstance(mapping_page, AccountMappingPage):
            return

        mappings = mapping_page.get_mappings()

        if mappings:
            first_mapping = mappings[0]
            self._show_preview(first_mapping)

            total_files = len(mappings)
            self.summary_label.setText(
                f"Importing {total_files} file(s). Showing preview of first file: {first_mapping.file_info.name}"
            )

    def _show_preview(self, mapping: ImportFileMapping):
        if mapping.error:
            self.table.setRowCount(1)
            self.table.setColumnCount(1)
            self.table.setItem(0, 0, QTableWidgetItem(f"Error: {mapping.error}"))
            return

        if not mapping.preview_rows:
            self.table.setRowCount(1)
            self.table.setColumnCount(1)
            self.table.setItem(0, 0, QTableWidgetItem("No preview data available"))
            return

        columns = list(mapping.preview_rows[0].keys())

        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(mapping.preview_rows))

        for row_idx, row_data in enumerate(mapping.preview_rows):
            for col_idx, col_name in enumerate(columns):
                value = str(row_data.get(col_name, ""))
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))
