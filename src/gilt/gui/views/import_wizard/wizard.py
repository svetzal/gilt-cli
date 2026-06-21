from __future__ import annotations

from PySide6.QtWidgets import QMessageBox, QWizard

from gilt.gui.services.import_service import ImportService
from gilt.gui.views.categorization_review_page import CategorizationReviewPage
from gilt.gui.views.duplicate_review_page import DuplicateReviewPage
from gilt.gui.views.import_wizard._page_ids import (
    PAGE_ACCOUNT_MAPPING,
    PAGE_CATEGORIZATION_REVIEW,
    PAGE_DUPLICATE_REVIEW,
    PAGE_EXECUTE,
    PAGE_OPTIONS,
    PAGE_PREVIEW,
    PAGE_SELECT_FILES,
)
from gilt.gui.views.import_wizard.pages.account_mapping_page import AccountMappingPage
from gilt.gui.views.import_wizard.pages.execute_page import ExecutePage
from gilt.gui.views.import_wizard.pages.file_selection_page import FileSelectionPage
from gilt.gui.views.import_wizard.pages.options_page import OptionsPage
from gilt.gui.views.import_wizard.pages.preview_page import PreviewPage


class ImportWizard(QWizard):
    """Wizard for importing CSV files."""

    def __init__(self, service: ImportService, parent=None):
        super().__init__(parent)

        self.service = service

        self.setWindowTitle("Import CSV Files")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnLastPage, True)
        self.setMinimumSize(800, 600)

        self.setPage(PAGE_SELECT_FILES, FileSelectionPage(service))
        self.setPage(PAGE_ACCOUNT_MAPPING, AccountMappingPage(service))
        self.setPage(PAGE_PREVIEW, PreviewPage(service))
        self.setPage(PAGE_DUPLICATE_REVIEW, DuplicateReviewPage(service))
        self.setPage(PAGE_CATEGORIZATION_REVIEW, CategorizationReviewPage(service))
        self.setPage(PAGE_OPTIONS, OptionsPage())
        self.setPage(PAGE_EXECUTE, ExecutePage())

    def reject(self):
        """Handle wizard cancellation — stop any running worker before closing."""
        execute_page = self.page(PAGE_EXECUTE)
        if isinstance(execute_page, ExecutePage):
            execute_page.cleanupPage()
        super().reject()

    def accept(self):
        """Handle wizard acceptance."""
        execute_page = self.page(PAGE_EXECUTE)
        if isinstance(execute_page, ExecutePage):
            if execute_page.import_successful:
                super().accept()
            else:
                reply = QMessageBox.question(
                    self,
                    "Import Failed",
                    "The import operation failed. Do you want to close the wizard?",
                    QMessageBox.Yes | QMessageBox.No,
                )
                if reply == QMessageBox.Yes:
                    super().accept()
        else:
            super().accept()
