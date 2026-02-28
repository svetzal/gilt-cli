from __future__ import annotations

"""
Import Wizard - Multi-step wizard for importing CSV files

Guides users through:
1. File selection (with drag-and-drop)
2. Account mapping
3. Preview & verification
4. Import options
5. Execution & review
"""

from pathlib import Path

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QListWidget,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from gilt.gui.services.import_service import ImportFileMapping, ImportResult, ImportService
from gilt.gui.views.categorization_review_page import CategorizationReviewPage
from gilt.gui.views.duplicate_review_page import DuplicateReviewPage

# Page IDs
PAGE_SELECT_FILES = 0
PAGE_ACCOUNT_MAPPING = 1
PAGE_PREVIEW = 2
PAGE_DUPLICATE_REVIEW = 3
PAGE_CATEGORIZATION_REVIEW = 4
PAGE_OPTIONS = 5
PAGE_EXECUTE = 6


class ImportWorker(QThread):
    """Worker thread for import operations."""

    progress = Signal(int)  # 0-100
    finished = Signal(object)  # ImportResult
    error = Signal(str)

    def __init__(
        self,
        service: ImportService,
        mappings: list[ImportFileMapping],
        write: bool,
        exclude_ids: list[str] | None = None,
        categorization_map: dict[str, str] | None = None,
    ):
        super().__init__()
        self.service = service
        self.mappings = mappings
        self.write = write
        self.exclude_ids = exclude_ids
        self.categorization_map = categorization_map

    def run(self):
        """Execute the import operation."""
        try:
            total_imported = 0
            total_duplicates = 0
            all_messages = []

            for i, mapping in enumerate(self.mappings):
                if not mapping.selected_account_id:
                    continue

                # Progress: allocate equal portions to each file
                file_progress_start = int((i / len(self.mappings)) * 100)
                file_progress_end = int(((i + 1) / len(self.mappings)) * 100)

                def progress_callback(pct, _start=file_progress_start, _end=file_progress_end):
                    overall = _start + int(
                        (pct / 100) * (_end - _start)
                    )
                    self.progress.emit(overall)

                result = self.service.import_file(
                    mapping.file_info.path,
                    mapping.selected_account_id,
                    write=self.write,
                    progress_callback=progress_callback,
                    exclude_ids=self.exclude_ids,
                    categorization_map=self.categorization_map,
                )

                total_imported += result.imported_count
                total_duplicates += result.duplicate_count
                all_messages.extend(result.messages)

                if not result.success:
                    # Early exit on error
                    self.finished.emit(
                        ImportResult(
                            success=False,
                            imported_count=total_imported,
                            duplicate_count=total_duplicates,
                            error_count=1,
                            messages=all_messages,
                        )
                    )
                    return

            self.progress.emit(100)
            self.finished.emit(
                ImportResult(
                    success=True,
                    imported_count=total_imported,
                    duplicate_count=total_duplicates,
                    error_count=0,
                    messages=all_messages,
                )
            )

        except Exception as e:
            self.error.emit(str(e))


class FileSelectionPage(QWizardPage):
    """Step 1: Select CSV files to import."""

    def __init__(self, service: ImportService):
        super().__init__()
        self.service = service

        self.setTitle("Select CSV Files")
        self.setSubTitle(
            "Choose one or more bank CSV files to import. You can drag and drop files or use the file browser."
        )

        self.selected_files: list[Path] = []

        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # File list
        list_label = QLabel("Selected Files:")
        layout.addWidget(list_label)

        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setDragDropMode(QListWidget.InternalMove)
        layout.addWidget(self.file_list)

        # Enable drag-and-drop
        self.file_list.dragEnterEvent = self._drag_enter_event
        self.file_list.dropEvent = self._drop_event

        # Buttons
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add Files...")
        self.add_btn.clicked.connect(self._on_add_files)
        button_layout.addWidget(self.add_btn)

        self.remove_btn = QPushButton("Remove Selected")
        self.remove_btn.clicked.connect(self._on_remove_files)
        self.remove_btn.setEnabled(False)
        button_layout.addWidget(self.remove_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        # Info label
        self.info_label = QLabel("<i>No files selected</i>")
        # Use system palette for disabled text color instead of hardcoded gray
        self.info_label.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(self.info_label)

        # Connect signals
        self.file_list.itemSelectionChanged.connect(self._on_selection_changed)

    def _drag_enter_event(self, event: QDragEnterEvent):
        """Handle drag enter event."""
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop_event(self, event: QDropEvent):
        """Handle drop event."""
        urls = event.mimeData().urls()
        for url in urls:
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() == ".csv" and path not in self.selected_files:
                self.selected_files.append(path)
                self.file_list.addItem(path.name)

        self._update_info()
        self.completeChanged.emit()

    def _on_add_files(self):
        """Handle add files button click."""
        file_paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Select CSV Files",
            str(Path.home()),
            "CSV Files (*.csv);;All Files (*)",
        )

        for file_path in file_paths:
            path = Path(file_path)
            if path not in self.selected_files:
                self.selected_files.append(path)
                self.file_list.addItem(path.name)

        self._update_info()
        self.completeChanged.emit()

    def _on_remove_files(self):
        """Handle remove files button click."""
        selected_items = self.file_list.selectedItems()
        for item in selected_items:
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
            if row < len(self.selected_files):
                self.selected_files.pop(row)

        self._update_info()
        self.completeChanged.emit()

    def _on_selection_changed(self):
        """Handle selection change."""
        has_selection = len(self.file_list.selectedItems()) > 0
        self.remove_btn.setEnabled(has_selection)

    def _update_info(self):
        """Update info label."""
        count = len(self.selected_files)
        if count == 0:
            self.info_label.setText("<i>No files selected</i>")
        elif count == 1:
            self.info_label.setText("<i>1 file selected</i>")
        else:
            self.info_label.setText(f"<i>{count} files selected</i>")

    def isComplete(self) -> bool:
        """Check if page is complete."""
        return len(self.selected_files) > 0

    def get_selected_files(self) -> list[Path]:
        """Get selected file paths."""
        return self.selected_files


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
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Mapping table
        self.table = QTableWidget()
        self.table.setColumnCount(4)
        self.table.setHorizontalHeaderLabels(["File", "Detected Account", "Import To", "Status"])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Make all columns resizable by user
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        # Auto-resize rows to fit content (including the combo box)
        self.table.verticalHeader().setSectionResizeMode(QHeaderView.ResizeToContents)

        # Set initial default widths
        header.resizeSection(0, 250)  # File
        header.resizeSection(1, 150)  # Detected Account
        header.resizeSection(2, 150)  # Import To
        header.resizeSection(3, 100)  # Status

        layout.addWidget(self.table)

        # Info
        info = QLabel(
            "<i>Auto-detected accounts are shown. You can change the target account "
            "using the dropdown in the 'Import To' column.</i>"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: palette(placeholder-text); padding: 8px;")
        layout.addWidget(info)

    def initializePage(self):
        """Initialize page when shown."""
        # Get selected files from previous page
        wizard = self.wizard()
        if not isinstance(wizard, ImportWizard):
            return

        file_selection_page = wizard.page(PAGE_SELECT_FILES)
        if not isinstance(file_selection_page, FileSelectionPage):
            return

        selected_files = file_selection_page.get_selected_files()

        # Create mappings
        self.mappings = []
        self.table.setRowCount(0)

        accounts = self.service.get_accounts()
        account_ids = [acc.account_id for acc in accounts]

        for file_path in selected_files:
            mapping = self.service.create_file_mapping(file_path, max_preview_rows=3)
            self.mappings.append(mapping)

            # Add row
            row = self.table.rowCount()
            self.table.insertRow(row)

            # File name
            self.table.setItem(row, 0, QTableWidgetItem(mapping.file_info.name))

            # Detected account
            detected = (
                mapping.detected_account.account_id if mapping.detected_account else "Unknown"
            )
            self.table.setItem(row, 1, QTableWidgetItem(detected))

            # Account selector
            combo = QComboBox()
            combo.addItems(account_ids)
            if mapping.selected_account_id:
                index = combo.findText(mapping.selected_account_id)
                if index >= 0:
                    combo.setCurrentIndex(index)
            combo.currentTextChanged.connect(lambda text, r=row: self._on_account_changed(r, text))
            self.table.setCellWidget(row, 2, combo)

            # Status
            status = "✓ Ready" if mapping.selected_account_id else "⚠ Unknown"
            status_item = QTableWidgetItem(status)
            if not mapping.selected_account_id:
                status_item.setForeground(Qt.red)
            self.table.setItem(row, 3, status_item)

    def _on_account_changed(self, row: int, account_id: str):
        """Handle account selection change."""
        if row < len(self.mappings):
            self.mappings[row].selected_account_id = account_id

            # Update status
            status_item = self.table.item(row, 3)
            if status_item:
                status_item.setText("✓ Ready")
                status_item.setForeground(Qt.black)

        self.completeChanged.emit()

    def isComplete(self) -> bool:
        """Check if page is complete."""
        # All files must have an account selected
        return all(m.selected_account_id for m in self.mappings)

    def get_mappings(self) -> list[ImportFileMapping]:
        """Get file mappings."""
        return self.mappings


class PreviewPage(QWizardPage):
    """Step 3: Preview transactions."""

    def __init__(self, service: ImportService):
        super().__init__()
        self.service = service

        self.setTitle("Preview & Verify")
        self.setSubTitle("Review the files and preview data before importing.")

        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Summary
        self.summary_label = QLabel()
        self.summary_label.setStyleSheet("font-weight: bold;")
        layout.addWidget(self.summary_label)

        # Preview table
        self.table = QTableWidget()
        self.table.setAlternatingRowColors(True)
        # Make columns resizable by user
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        layout.addWidget(self.table)

        # Warning
        warning = QLabel(
            "⚠ <b>Note:</b> This is a preview of the raw CSV data. "
            "The actual import will normalize column names and detect duplicates."
        )
        warning.setWordWrap(True)
        # Use semi-transparent background to tint the theme color instead of hardcoded yellow
        # and use standard text color
        warning.setStyleSheet(
            "background-color: rgba(255, 243, 205, 0.2); "  # Subtle yellow tint
            "color: palette(text); "
            "padding: 8px; "
            "border-radius: 4px; "
            "border: 1px solid palette(mid);"
        )
        layout.addWidget(warning)

    def initializePage(self):
        """Initialize page when shown."""
        wizard = self.wizard()
        if not isinstance(wizard, ImportWizard):
            return

        mapping_page = wizard.page(PAGE_ACCOUNT_MAPPING)
        if not isinstance(mapping_page, AccountMappingPage):
            return

        mappings = mapping_page.get_mappings()

        # Show preview of first file
        if mappings:
            first_mapping = mappings[0]
            self._show_preview(first_mapping)

            # Update summary
            total_files = len(mappings)
            self.summary_label.setText(
                f"Importing {total_files} file(s). Showing preview of first file: {first_mapping.file_info.name}"
            )

    def _show_preview(self, mapping: ImportFileMapping):
        """Show preview of a file."""
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

        # Get columns from first row
        columns = list(mapping.preview_rows[0].keys())

        self.table.setColumnCount(len(columns))
        self.table.setHorizontalHeaderLabels(columns)
        self.table.setRowCount(len(mapping.preview_rows))

        for row_idx, row_data in enumerate(mapping.preview_rows):
            for col_idx, col_name in enumerate(columns):
                value = str(row_data.get(col_name, ""))
                self.table.setItem(row_idx, col_idx, QTableWidgetItem(value))


class OptionsPage(QWizardPage):
    """Step 4: Import options."""

    def __init__(self):
        super().__init__()

        self.setTitle("Import Options")
        self.setSubTitle("Configure how the import should be performed.")

        self._init_ui()

    def _init_ui(self):
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Options group
        group = QGroupBox("Import Settings")
        group_layout = QVBoxLayout(group)

        # Write checkbox
        self.write_check = QCheckBox("Write changes to ledger files (uncheck for dry-run)")
        self.write_check.setChecked(False)  # Default to dry-run
        group_layout.addWidget(self.write_check)

        # Info about dry-run
        dry_run_info = QLabel(
            "If unchecked, the import will run in simulation mode. No files will be modified."
        )
        dry_run_info.setWordWrap(True)
        dry_run_info.setStyleSheet("color: palette(placeholder-text); padding-left: 20px;")
        group_layout.addWidget(dry_run_info)

        group_layout.addSpacing(10)

        # Note about duplicates
        duplicate_info = QLabel(
            "ℹ <b>Duplicate Detection:</b> Transactions are automatically deduplicated "
            "based on their transaction ID (hash of account, date, amount, and description). "
            "Existing transactions will not be re-imported."
        )
        duplicate_info.setWordWrap(True)
        duplicate_info.setStyleSheet(
            "background-color: rgba(209, 236, 241, 0.2); "  # Subtle blue tint
            "color: palette(text); "
            "padding: 8px; "
            "border-radius: 4px; "
            "border: 1px solid palette(mid);"
        )
        group_layout.addWidget(duplicate_info)

        layout.addWidget(group)
        layout.addStretch()

    def get_write_enabled(self) -> bool:
        """Check if write mode is enabled."""
        return self.write_check.isChecked()


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
        """Initialize UI."""
        layout = QVBoxLayout(self)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        # Log output
        log_label = QLabel("Import Log:")
        layout.addWidget(log_label)

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        layout.addWidget(self.log_text)

        # Summary
        self.summary_label = QLabel()
        self.summary_label.setWordWrap(True)
        self.summary_label.setStyleSheet("font-weight: bold; padding: 8px;")
        layout.addWidget(self.summary_label)

    def initializePage(self):
        """Initialize page when shown."""
        # Reset state
        self.import_complete = False
        self.import_successful = False
        self.progress_bar.setValue(0)
        self.log_text.clear()
        self.summary_label.clear()

        # Get wizard data
        wizard = self.wizard()
        if not isinstance(wizard, ImportWizard):
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

        # Get excluded IDs
        exclude_ids = set()
        if isinstance(duplicate_page, DuplicateReviewPage):
            exclude_ids = duplicate_page.get_excluded_ids()

        # Get categorization decisions
        categorization_map = {}
        cat_page = wizard.page(PAGE_CATEGORIZATION_REVIEW)
        if isinstance(cat_page, CategorizationReviewPage):
            items = cat_page.get_categorization_decisions()
            for item in items:
                if item.assigned_category:
                    categorization_map[item.transaction.transaction_id] = item.assigned_category

        # Start import
        self._start_import(wizard.service, mappings, write_enabled, exclude_ids, categorization_map)

    def _start_import(
        self,
        service: ImportService,
        mappings: list[ImportFileMapping],
        write: bool,
        exclude_ids: set[str] = None,
        categorization_map: dict[str, str] = None,
    ):
        """Start the import operation in a background thread."""
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
        """Handle progress update."""
        self.progress_bar.setValue(value)

    def _on_finished(self, result: ImportResult):
        """Handle import completion."""
        self.import_complete = True
        self.import_successful = result.success

        # Show messages
        for msg in result.messages:
            self._log(msg)

        # Show summary
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
        """Handle import error."""
        self.import_complete = True
        self.import_successful = False

        self._log(f"ERROR: {error}")
        self.summary_label.setText(f"✗ <span style='color: red;'>Import failed: {error}</span>")

        self.completeChanged.emit()

    def _log(self, message: str):
        """Add a message to the log."""
        self.log_text.append(message)

    def isComplete(self) -> bool:
        """Check if page is complete."""
        return self.import_complete


class ImportWizard(QWizard):
    """Wizard for importing CSV files."""

    def __init__(self, service: ImportService, parent=None):
        super().__init__(parent)

        self.service = service

        self.setWindowTitle("Import CSV Files")
        self.setWizardStyle(QWizard.ModernStyle)
        self.setOption(QWizard.NoBackButtonOnLastPage, True)
        self.setMinimumSize(800, 600)

        # Add pages
        self.setPage(PAGE_SELECT_FILES, FileSelectionPage(service))
        self.setPage(PAGE_ACCOUNT_MAPPING, AccountMappingPage(service))
        self.setPage(PAGE_PREVIEW, PreviewPage(service))
        self.setPage(PAGE_DUPLICATE_REVIEW, DuplicateReviewPage(service))
        self.setPage(PAGE_CATEGORIZATION_REVIEW, CategorizationReviewPage(service))
        self.setPage(PAGE_OPTIONS, OptionsPage())
        self.setPage(PAGE_EXECUTE, ExecutePage())

    def accept(self):
        """Handle wizard acceptance."""
        execute_page = self.page(PAGE_EXECUTE)
        if isinstance(execute_page, ExecutePage):
            if execute_page.import_successful:
                super().accept()
            else:
                # Don't close wizard if import failed
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
