from __future__ import annotations

from PySide6.QtWidgets import (
    QLabel,
    QProgressBar,
    QTextEdit,
    QVBoxLayout,
    QWizardPage,
)

from gilt.gui.services.import_service import ImportFileMapping, ImportResult, ImportService
from gilt.gui.views.import_wizard._page_ids import (
    PAGE_ACCOUNT_MAPPING,
    PAGE_CATEGORIZATION_REVIEW,
    PAGE_DUPLICATE_REVIEW,
    PAGE_OPTIONS,
)
from gilt.gui.views.import_wizard.pages.account_mapping_page import AccountMappingPage
from gilt.gui.views.import_wizard.pages.options_page import OptionsPage
from gilt.gui.workers.import_worker import ImportWorker


class ExecutePage(QWizardPage):
    """Step 5: Execute and review."""

    def __init__(self):
        super().__init__()

        self.setTitle("Import Progress")
        self.setSubTitle("Importing files...")

        self.import_complete = False
        self.import_successful = False
        self.worker: ImportWorker | None = None

        self._init_ui()

    def _init_ui(self):
        layout = QVBoxLayout(self)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        log_label = QLabel("Import Log:")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(self.summary_label)

    def initializePage(self):
        self.import_complete = False
        self.import_successful = False
        self.progress_bar.setValue(0)
        self.log_text.clear()
        self.summary_label.clear()

        wizard = self.wizard()
        if wizard is None or not hasattr(wizard, "service"):
            return

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        options_page = wizard.page(PAGE_OPTIONS)
        duplicate_page = wizard.page(PAGE_DUPLICATE_REVIEW)

        if not isinstance(mapping_page, AccountMappingPage):
            return
        if not isinstance(options_page, OptionsPage):
            return

        mappings = mapping_page.get_mappings()
        write_enabled = options_page.get_write_enabled()

        exclude_ids = set()
        from gilt.gui.views.duplicate_review_page import DuplicateReviewPage

        if isinstance(duplicate_page, DuplicateReviewPage):
            exclude_ids = duplicate_page.get_excluded_ids()

        categorization_map = {}
        from gilt.gui.views.categorization_review_page import CategorizationReviewPage

        cat_page = wizard.page(PAGE_CATEGORIZATION_REVIEW)
        if isinstance(cat_page, CategorizationReviewPage):
            items = cat_page.get_categorization_decisions()
            for item in items:
                if item.assigned_category:
                    categorization_map[item.transaction.transaction_id] = item.assigned_category

        self._start_import(wizard.service, mappings, write_enabled, exclude_ids, categorization_map)

    def cleanupPage(self):
        """Stop worker if running when user navigates back or cancels wizard."""
        if self.worker and self.worker.isRunning():
            self.worker.progress.disconnect(self._on_progress)
            self.worker.finished.disconnect(self._on_finished)
            self.worker.error.disconnect(self._on_error)
            self.worker.requestInterruption()
            self.worker.wait(2000)
        super().cleanupPage()

    def _start_import(
        self,
        service: ImportService,
        mappings: list[ImportFileMapping],
        write: bool,
        exclude_ids: set[str] = None,
        categorization_map: dict[str, str] = None,
    ):
        exclude_list = list(exclude_ids) if exclude_ids else None
        self.worker = ImportWorker(service, mappings, write, exclude_list, categorization_map)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_finished)
        self.worker.error.connect(self._on_error)
        self.worker.start()

        mode = "WRITE" if write else "DRY-RUN"
        self._log(f"Starting import in {mode} mode...")
        if exclude_ids:
            self._log(f"Skipping {len(exclude_ids)} duplicate transaction(s)...")
        if categorization_map:
            self._log(f"Applying {len(categorization_map)} category assignment(s)...")
        self._log(f"Processing {len(mappings)} file(s)...\n")

    def _on_progress(self, value: int):
        self.progress_bar.setValue(value)

    def _on_finished(self, result: ImportResult):
        self.import_complete = True
        self.import_successful = result.success

        for msg in result.messages:
            self._log(msg)

        if result.success:
            self.summary_label.setText(
                f"✓ <span style='color: green;'>Import completed successfully!</span><br>"
                f"Imported: {result.imported_count} transaction(s)<br>"
                f"Duplicates skipped: {result.duplicate_count}"
            )
        else:
            self.summary_label.setText(
                f"✗ <span style='color: red;'>Import failed</span><br>Errors: {result.error_count}"
            )

        self.completeChanged.emit()

    def _on_error(self, error: str):
        self.import_complete = True
        self.import_successful = False

        self._log(f"ERROR: {error}")
        self.summary_label.setText(f"✗ <span style='color: red;'>Import failed: {error}</span>")

        self.completeChanged.emit()

    def _log(self, message: str):
        self.log_text.append(message)

    def isComplete(self) -> bool:
        return self.import_complete
