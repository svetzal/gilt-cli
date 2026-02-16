from __future__ import annotations
from typing import List, Optional

from PySide6.QtWidgets import QStyledItemDelegate
from PySide6.QtCore import Qt, QAbstractProxyModel

from gilt.gui.widgets.smart_category_combo import SmartCategoryComboBox
from gilt.gui.models.transaction_model import TransactionTableModel


class CategoryDelegate(QStyledItemDelegate):
    """Delegate for smart category selection in table."""

    def __init__(self, parent=None, all_categories: Optional[List[str]] = None):
        super().__init__(parent)
        self.all_categories = all_categories or []

    def createEditor(self, parent, option, index):
        editor = SmartCategoryComboBox(parent)

        # Try to get suggestions from model metadata
        suggestions = []

        # Handle proxy models to get to the source TransactionTableModel
        model = index.model()
        idx = index

        while isinstance(model, QAbstractProxyModel):
            idx = model.mapToSource(idx)
            model = model.sourceModel()

        # Now model should be TransactionTableModel
        if isinstance(model, TransactionTableModel):
            group = model.get_transaction(idx.row())
            if group:
                txn_id = group.primary.transaction_id
                meta = model.get_metadata(txn_id)

                pred_cat = meta.get("predicted_category")
                conf = meta.get("confidence")

                if pred_cat:
                    suggestions.append((pred_cat, conf))

        editor.set_categories(self.all_categories, suggestions)
        return editor

    def setEditorData(self, editor, index):
        current_val = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        editor.setCurrentData(current_val)

    def setModelData(self, editor, model, index):
        new_val = editor.currentData()
        model.setData(index, new_val, Qt.ItemDataRole.EditRole)

    def updateEditorGeometry(self, editor, option, index):
        editor.setGeometry(option.rect)
