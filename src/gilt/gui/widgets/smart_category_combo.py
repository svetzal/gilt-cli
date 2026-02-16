from __future__ import annotations
from typing import List, Tuple, Optional

from PySide6.QtWidgets import QComboBox, QCompleter
from PySide6.QtCore import Qt
from PySide6.QtGui import QStandardItemModel, QStandardItem, QBrush

from gilt.gui.theme import Theme


class SmartCategoryComboBox(QComboBox):
    """
    Smart ComboBox for category selection.

    Features:
    - Shows suggested categories at the top with confidence scores.
    - Shows all categories below.
    - Fuzzy search (substring matching).
    """

    def __init__(self, parent=None):
        super().__init__(parent)

        self.setEditable(True)
        self.setInsertPolicy(QComboBox.InsertPolicy.NoInsert)

        # Setup model
        self._model = QStandardItemModel(self)
        self.setModel(self._model)

        # Setup completer for filtering
        completer = self.completer()
        if completer:
            completer.setCompletionMode(QCompleter.CompletionMode.PopupCompletion)
            completer.setFilterMode(Qt.MatchFlag.MatchContains)
            completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
            # Ensure completer uses the same model
            completer.setModel(self._model)

    def set_categories(
        self,
        all_categories: List[str],
        suggestions: Optional[List[Tuple[str, Optional[float]]]] = None,
        placeholder: Optional[str] = None,
    ):
        """
        Populate the combo box.

        Args:
            all_categories: List of all category names.
            suggestions: List of (category_name, confidence) tuples. Confidence can be None.
            placeholder: Optional placeholder text (e.g. "-- Select --").
        """
        self.clear()
        self._model.clear()

        # Placeholder
        if placeholder:
            item = QStandardItem(placeholder)
            item.setData(None, Qt.ItemDataRole.UserRole)
            self._model.appendRow(item)

        # 1. Suggestions Section
        if suggestions:
            # Header
            header = QStandardItem("--- Suggestions ---")
            header.setEnabled(False)
            header.setBackground(QBrush(Theme.color("header_bg")))
            header.setForeground(QBrush(Theme.color("header_fg")))
            header.setSelectable(False)
            self._model.appendRow(header)

            for cat, conf in suggestions:
                if conf is not None:
                    text = f"{cat} ({conf:.0%})"
                else:
                    text = cat

                item = QStandardItem(text)
                item.setData(cat, Qt.ItemDataRole.UserRole)
                item.setData(cat, Qt.ItemDataRole.EditRole)  # Text for line edit

                # Style
                font = item.font()
                font.setBold(True)
                item.setFont(font)
                item.setForeground(QBrush(Theme.color("success_fg")))
                item.setBackground(QBrush(Theme.color("success_bg")))

                self._model.appendRow(item)

            # Separator
            sep = QStandardItem("--- All Categories ---")
            sep.setEnabled(False)
            sep.setBackground(QBrush(Theme.color("header_bg")))
            sep.setForeground(QBrush(Theme.color("header_fg")))
            sep.setSelectable(False)
            self._model.appendRow(sep)

        # 2. All Categories Section
        # Add "Select" placeholder if no suggestions?
        # Or just add all categories.

        for cat in all_categories:
            item = QStandardItem(cat)
            item.setData(cat, Qt.ItemDataRole.UserRole)
            item.setData(cat, Qt.ItemDataRole.EditRole)
            self._model.appendRow(item)

    def currentData(self, role=Qt.ItemDataRole.UserRole):
        """Get data for current index."""
        return super().currentData(role)

    def setCurrentData(self, data: str):
        """Set current index by data (category name)."""
        idx = self.findData(data, Qt.ItemDataRole.UserRole)
        if idx >= 0:
            self.setCurrentIndex(idx)
        else:
            # If not found, maybe clear selection or set text?
            self.setCurrentIndex(-1)
            self.setEditText(data if data else "")
