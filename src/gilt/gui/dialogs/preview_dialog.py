from __future__ import annotations

"""
Preview Dialog - Base class for preview-before-commit dialogs

Shows a table of changes before applying them, maintaining privacy and safety.
"""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
)

from gilt.gui.theme import Theme


class PreviewDialog(QDialog):
    """Base class for preview dialogs that show before/after changes."""

    def __init__(
        self,
        title: str,
        action_description: str,
        column_headers: list[str],
        parent=None,
    ):
        """
        Initialize preview dialog.

        Args:
            title: Dialog window title
            action_description: Description of the action being previewed
            column_headers: List of column headers for the preview table
            parent: Parent widget
        """
        super().__init__(parent)

        self.setWindowTitle(title)
        self.setMinimumWidth(800)
        self.setMinimumHeight(500)
        self.setModal(True)

        self.column_headers = column_headers
        self._init_ui(action_description)

    def _init_ui(self, action_description: str):
        """
        Initialize the user interface.

        Args:
            action_description: Description of the action
        """
        layout = QVBoxLayout(self)

        # Action description
        desc_label = QLabel(f"<b>Action:</b> {action_description}")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label)

        # Preview table
        self.table = QTableWidget()
        self.table.setColumnCount(len(self.column_headers))
        self.table.setHorizontalHeaderLabels(self.column_headers)
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Configure header - make all columns resizable by user
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)

        layout.addWidget(self.table)

        # Warning/info section
        self.warning_container = QVBoxLayout()
        layout.addLayout(self.warning_container)

        # Confirmation checkbox
        self.confirm_check = QCheckBox("I understand these changes will be permanent")
        layout.addWidget(self.confirm_check)

        # Buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()

        # Dialog buttons
        self.buttons = QDialogButtonBox(QDialogButtonBox.Cancel)

        # Apply button (initially disabled)
        self.apply_btn = QPushButton("Apply Changes")
        self.apply_btn.setEnabled(False)
        self.apply_btn.clicked.connect(self.accept)
        self.buttons.addButton(self.apply_btn, QDialogButtonBox.AcceptRole)

        # Cancel button
        self.buttons.rejected.connect(self.reject)

        button_layout.addWidget(self.buttons)
        layout.addLayout(button_layout)

        # Connect confirmation checkbox
        self.confirm_check.stateChanged.connect(self._on_confirm_changed)

    def _on_confirm_changed(self, state):
        """Enable/disable apply button based on confirmation checkbox."""
        self.apply_btn.setEnabled(state == Qt.Checked)

    def add_row(self, values: list[str], highlight_columns: list[int] = None):
        """
        Add a row to the preview table.

        Args:
            values: List of cell values (must match column count)
            highlight_columns: Optional list of column indices to highlight
        """
        if len(values) != len(self.column_headers):
            raise ValueError(f"Expected {len(self.column_headers)} values, got {len(values)}")

        row = self.table.rowCount()
        self.table.insertRow(row)

        for col, value in enumerate(values):
            item = QTableWidgetItem(value)

            # Highlight specific columns
            if highlight_columns and col in highlight_columns:
                item.setBackground(Theme.color("highlight_bg"))

            self.table.setItem(row, col, item)

    def set_row_count_label(self, count: int):
        """
        Set a label showing the number of affected rows.

        Args:
            count: Number of rows/transactions
        """
        count_label = QLabel(
            f"<b>{count}</b> transaction{'s' if count != 1 else ''} will be affected"
        )
        count_label.setStyleSheet("font-size: 12pt; padding: 10px;")
        self.warning_container.addWidget(count_label)

    def add_warning(self, message: str):
        """
        Add a warning message to the dialog.

        Args:
            message: Warning message
        """
        warning_label = QLabel(f"⚠️  <b>Warning:</b> {message}")
        warning_label.setWordWrap(True)
        warning_label.setStyleSheet(
            "background-color: rgba(255, 243, 205, 0.2); "  # Subtle yellow tint
            "color: palette(text); "
            "border: 1px solid palette(mid); "
            "padding: 10px; border-radius: 4px;"
        )
        self.warning_container.addWidget(warning_label)

    def add_info(self, message: str):
        """
        Add an info message to the dialog.

        Args:
            message: Info message
        """
        info_label = QLabel(f"ℹ️  {message}")
        info_label.setWordWrap(True)
        info_label.setStyleSheet(
            "background-color: rgba(209, 236, 241, 0.2); "  # Subtle blue tint
            "color: palette(text); "
            "border: 1px solid palette(mid); "
            "padding: 10px; border-radius: 4px;"
        )
        self.warning_container.addWidget(info_label)

    def clear_rows(self):
        """Clear all rows from the table."""
        self.table.setRowCount(0)
