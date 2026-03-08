from __future__ import annotations

"""
Background Task Widget - Compact progress indicator for the status bar.

Shows a label + progress bar during background tasks, hides when idle.
"""

from PySide6.QtWidgets import QHBoxLayout, QLabel, QProgressBar, QWidget


class BackgroundTaskWidget(QWidget):
    """Compact progress widget for the main window status bar."""

    def __init__(self, parent=None):
        super().__init__(parent)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self._label = QLabel()
        layout.addWidget(self._label)

        self._progress_bar = QProgressBar()
        self._progress_bar.setFixedWidth(150)
        self._progress_bar.setTextVisible(False)
        layout.addWidget(self._progress_bar)

        self.setVisible(False)

    def start_task(self, description: str, total: int):
        """Show widget and initialize progress range."""
        self._label.setText(description)
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(0)
        self.setVisible(True)

    def update_progress(self, current: int, total: int):
        """Update the progress bar value and range."""
        self._progress_bar.setRange(0, total)
        self._progress_bar.setValue(current)

    def update_status(self, text: str):
        """Update the label text for phase changes."""
        self._label.setText(text)

    def finish_task(self):
        """Hide the widget."""
        self.setVisible(False)
