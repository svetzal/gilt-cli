from __future__ import annotations

"""
Categorize Dialog - Dialog for categorizing transactions with preview

Shows preview of category changes before applying them.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QHBoxLayout,
    QLabel,
    QVBoxLayout,
)

from gilt.gui.dialogs.preview_dialog import PreviewDialog
from gilt.gui.services.category_service import CategoryService
from gilt.gui.widgets.smart_category_combo import SmartCategoryComboBox
from gilt.model.account import TransactionGroup


class CategorizeDialog(PreviewDialog):
    """Dialog for categorizing transactions with preview."""

    def __init__(
        self,
        transactions: list[TransactionGroup],
        categories_config_path: Path,
        parent=None,
        suggested_category: tuple[str, str | None] | None = None,
    ):
        """
        Initialize categorize dialog.

        Args:
            transactions: List of transactions to categorize
            categories_config_path: Path to categories.yml
            parent: Parent widget
            suggested_category: Optional (category, subcategory) suggestion
        """
        self.transactions = transactions
        self.category_service = CategoryService(categories_config_path)
        self.selected_category = None
        self.selected_subcategory = None
        self.suggested_category = suggested_category

        # Column headers for preview table
        headers = [
            "Date",
            "Description",
            "Amount",
            "Current",
            "→ New Category",
        ]

        super().__init__(
            title="Categorize Transactions",
            action_description=f"Categorize {len(transactions)} transaction(s)",
            column_headers=headers,
            parent=parent,
        )

        # Add category selector at the top (before preview table)
        self._add_category_selector()

        # Apply suggestion if provided
        if self.suggested_category:
            cat, sub = self.suggested_category
            if cat:
                idx = self.category_combo.findData(cat)
                if idx >= 0:
                    self.category_combo.setCurrentIndex(idx)
                    # Subcategory is populated by signal handler, but we need to set it
                    # We might need to wait or manually trigger?
                    # Since signals are synchronous in direct calls usually,
                    # let's try setting it immediately after.
                    if sub:
                        sub_idx = self.subcategory_combo.findData(sub)
                        if sub_idx >= 0:
                            self.subcategory_combo.setCurrentIndex(sub_idx)

        # Populate preview
        self._populate_preview()

    def _add_category_selector(self):
        """Add category/subcategory selector to the dialog."""
        # Get the main layout
        main_layout = self.layout()

        # Create category selector layout
        selector_layout = QVBoxLayout()

        # Category combo
        cat_layout = QHBoxLayout()
        cat_layout.addWidget(QLabel("Category:"))

        self.category_combo = SmartCategoryComboBox()

        # Load categories
        categories = [c.name for c in self.category_service.get_all_categories()]

        suggestions = []
        if self.suggested_category and self.suggested_category[0]:
            suggestions.append((self.suggested_category[0], None))

        self.category_combo.set_categories(
            categories,
            suggestions=suggestions if suggestions else None,
            placeholder="-- Select Category --",
        )

        self.category_combo.currentIndexChanged.connect(self._on_category_changed)
        cat_layout.addWidget(self.category_combo)
        cat_layout.addStretch()

        selector_layout.addLayout(cat_layout)

        # Subcategory combo
        subcat_layout = QHBoxLayout()
        subcat_layout.addWidget(QLabel("Subcategory:"))

        self.subcategory_combo = QComboBox()
        self.subcategory_combo.addItem("-- None --", None)
        self.subcategory_combo.setEnabled(False)
        self.subcategory_combo.currentIndexChanged.connect(self._populate_preview)
        subcat_layout.addWidget(self.subcategory_combo)
        subcat_layout.addStretch()

        selector_layout.addLayout(subcat_layout)

        # Insert at position 1 (after action description, before table)
        main_layout.insertLayout(1, selector_layout)

    def _on_category_changed(self, index):
        """Handle category selection change."""
        category_name = self.category_combo.currentData()

        # Block signals to prevent multiple preview updates
        self.subcategory_combo.blockSignals(True)

        # Update subcategory combo
        self.subcategory_combo.clear()
        self.subcategory_combo.addItem("-- None --", None)

        if category_name:
            category = self.category_service.find_category(category_name)
            if category and category.subcategories:
                self.subcategory_combo.setEnabled(True)
                for subcat in category.subcategories:
                    self.subcategory_combo.addItem(subcat.name, subcat.name)
            else:
                self.subcategory_combo.setEnabled(False)
        else:
            self.subcategory_combo.setEnabled(False)

        self.subcategory_combo.blockSignals(False)

        # Update preview
        self._populate_preview()

    def _populate_preview(self):
        """Populate the preview table with transactions."""
        self.clear_rows()

        # Get selected category
        category_name = self.category_combo.currentData()
        subcategory_name = self.subcategory_combo.currentData()

        # Build new category string
        if category_name:
            if subcategory_name:
                new_category = f"{category_name}:{subcategory_name}"
            else:
                new_category = category_name
        else:
            new_category = "(none)"

        # Add rows for each transaction
        for group in self.transactions:
            txn = group.primary

            # Current category
            current = ""
            if txn.category:
                current = txn.category
                if txn.subcategory:
                    current += f":{txn.subcategory}"
            else:
                current = "(none)"

            # Add row
            self.add_row(
                [
                    str(txn.date),
                    txn.description or "",
                    f"{txn.amount:.2f}",
                    current,
                    new_category,
                ],
                highlight_columns=[4],  # Highlight new category column
            )

        # Update count label
        self.set_row_count_label(len(self.transactions))

        # Add warnings if re-categorizing
        recategorizing = any(
            t.primary.category and t.primary.category.strip() for t in self.transactions
        )
        if recategorizing:
            self.add_warning(
                "Some transactions already have categories. "
                "This will overwrite existing categorization."
            )

        # Disable apply if no category selected
        if not category_name:
            self.apply_btn.setEnabled(False)
            self.confirm_check.setEnabled(False)
            self.confirm_check.setChecked(False)
        else:
            self.confirm_check.setEnabled(True)
            self.confirm_check.setChecked(True)
            # Re-check confirmation state
            self._on_confirm_changed(self.confirm_check.checkState())

    def get_selected_category(self) -> tuple[str, str | None]:
        """
        Get the selected category and subcategory.

        Returns:
            Tuple of (category_name, subcategory_name or None)
        """
        category = self.category_combo.currentData()
        subcategory = self.subcategory_combo.currentData()
        return category, subcategory
