from __future__ import annotations

"""
Note Dialog - Dialog for editing transaction notes

Allows users to add or update notes on transactions.
"""

from PySide6.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QTextEdit,
    QPushButton,
    QDialogButtonBox,
)
from PySide6.QtCore import Qt


class NoteDialog(QDialog):
    """Dialog for editing transaction notes."""

    def __init__(self, current_note: str = "", transaction_desc: str = "", parent=None):
        """
        Initialize note dialog.

        Args:
            current_note: Current note text (empty string if no note)
            transaction_desc: Transaction description for context
            parent: Parent widget
        """
        super().__init__(parent)

        self.setWindowTitle("Edit Note")
        self.setMinimumWidth(500)
        self.setMinimumHeight(300)
        self.setModal(True)

        self._init_ui(current_note, transaction_desc)

    def _init_ui(self, current_note: str, transaction_desc: str):
        """
        Initialize the user interface.

        Args:
            current_note: Current note text
            transaction_desc: Transaction description
        """
        layout = QVBoxLayout(self)

        # Transaction info
        if transaction_desc:
            info_label = QLabel(f"<b>Transaction:</b> {transaction_desc}")
            info_label.setWordWrap(True)
            info_label.setStyleSheet("padding: 8px; background-color: #f0f0f0; border-radius: 4px;")
            layout.addWidget(info_label)

        # Note label
        note_label = QLabel("Note:")
        layout.addWidget(note_label)

        # Note text edit
        self.note_edit = QTextEdit()
        self.note_edit.setPlainText(current_note)
        self.note_edit.setPlaceholderText("Enter note for this transaction...")
        layout.addWidget(self.note_edit)

        # Hint label
        hint = QLabel("<i>Notes help you remember details about transactions.</i>")
        hint.setStyleSheet("color: gray; font-size: 10pt;")
        layout.addWidget(hint)

        # Buttons
        button_layout = QHBoxLayout()

        # Clear button
        clear_btn = QPushButton("Clear")
        clear_btn.clicked.connect(lambda: self.note_edit.clear())
        button_layout.addWidget(clear_btn)

        button_layout.addStretch()

        # Dialog buttons
        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        button_layout.addWidget(buttons)

        layout.addLayout(button_layout)

        # Focus on text edit
        self.note_edit.setFocus()

    def get_note(self) -> str:
        """
        Get the entered note text.

        Returns:
            Note text (trimmed)
        """
        return self.note_edit.toPlainText().strip()
