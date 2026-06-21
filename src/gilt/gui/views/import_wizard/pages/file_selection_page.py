from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import (
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QPushButton,
    QVBoxLayout,
    QWizardPage,
)

from gilt.gui.services.import_service import ImportService


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
        layout = QVBoxLayout(self)

        list_label = QLabel("Selected Files:")
        layout.addWidget(list_label)

        self.file_list = QListWidget()
        self.file_list.setAcceptDrops(True)
        self.file_list.setDragDropMode(QListWidget.InternalMove)
        layout.addWidget(self.file_list)

        self.file_list.dragEnterEvent = self._drag_enter_event
        self.file_list.dropEvent = self._drop_event

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

        self.info_label = QLabel("<i>No files selected</i>")
        self.info_label.setStyleSheet("color: palette(placeholder-text);")
        layout.addWidget(self.info_label)

        self.file_list.itemSelectionChanged.connect(self._on_selection_changed)

    def _drag_enter_event(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def _drop_event(self, event: QDropEvent):
        urls = event.mimeData().urls()
        for url in urls:
            path = Path(url.toLocalFile())
            if path.is_file() and path.suffix.lower() == ".csv" and path not in self.selected_files:
                self.selected_files.append(path)
                self.file_list.addItem(path.name)

        self._update_info()
        self.completeChanged.emit()

    def _on_add_files(self):
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
        selected_items = self.file_list.selectedItems()
        for item in selected_items:
            row = self.file_list.row(item)
            self.file_list.takeItem(row)
            if row < len(self.selected_files):
                self.selected_files.pop(row)

        self._update_info()
        self.completeChanged.emit()

    def _on_selection_changed(self):
        has_selection = len(self.file_list.selectedItems()) > 0
        self.remove_btn.setEnabled(has_selection)

    def _update_info(self):
        count = len(self.selected_files)
        if count == 0:
            self.info_label.setText("<i>No files selected</i>")
        elif count == 1:
            self.info_label.setText("<i>1 file selected</i>")
        else:
            self.info_label.setText(f"<i>{count} files selected</i>")

    def isComplete(self) -> bool:
        return len(self.selected_files) > 0

    def get_selected_files(self) -> list[Path]:
        return self.selected_files
