from __future__ import annotations

"""
Categories View - View for managing categories and budgets

Provides category management, budget setting, and usage statistics.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QMessageBox,
    QInputDialog,
    QApplication,
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QPalette

from gilt.gui.services.category_service import CategoryService
from gilt.model.category import BudgetPeriod
from gilt.gui.theme import Theme


class CategoriesView(QWidget):
    """View for managing categories."""

    # Signal emitted when categories are modified
    categories_modified = Signal()

    def __init__(self, config_path: Path, parent=None):
        super().__init__(parent)

        self.service = CategoryService(config_path)

        self._init_ui()
        self._load_categories()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("<h2>Categories & Budgets</h2>")
        layout.addWidget(title)

        # Action buttons
        button_layout = QHBoxLayout()

        self.add_btn = QPushButton("Add Category")
        self.add_btn.clicked.connect(self._on_add_category)
        button_layout.addWidget(self.add_btn)

        self.add_subcat_btn = QPushButton("Add Subcategory")
        self.add_subcat_btn.clicked.connect(self._on_add_subcategory)
        self.add_subcat_btn.setEnabled(False)
        button_layout.addWidget(self.add_subcat_btn)

        self.set_budget_btn = QPushButton("Set Budget")
        self.set_budget_btn.clicked.connect(self._on_set_budget)
        self.set_budget_btn.setEnabled(False)
        button_layout.addWidget(self.set_budget_btn)

        self.remove_btn = QPushButton("Remove")
        self.remove_btn.clicked.connect(self._on_remove)
        self.remove_btn.setEnabled(False)
        button_layout.addWidget(self.remove_btn)

        button_layout.addStretch()

        self.reload_btn = QPushButton("Reload")
        self.reload_btn.clicked.connect(self._load_categories)
        button_layout.addWidget(self.reload_btn)

        layout.addLayout(button_layout)

        # Categories table
        self.table = QTableWidget()
        self.table.setColumnCount(5)
        self.table.setHorizontalHeaderLabels(
            [
                "Category",
                "Subcategory",
                "Description",
                "Budget",
                "Period",
            ]
        )
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setSelectionMode(QTableWidget.SingleSelection)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Configure header - make all columns resizable by user
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)

        # Set initial default widths
        header.resizeSection(0, 150)  # Category
        header.resizeSection(1, 150)  # Subcategory
        header.resizeSection(2, 300)  # Description
        header.resizeSection(3, 120)  # Budget
        header.resizeSection(4, 100)  # Period

        self.table.itemSelectionChanged.connect(self._on_selection_changed)

        layout.addWidget(self.table)

        # Info label
        info = QLabel(
            "<i>Select a category to set budget or add subcategories. "
            "Changes are saved immediately.</i>"
        )
        info.setStyleSheet("color: palette(placeholder-text); padding: 8px;")
        layout.addWidget(info)

    def _load_categories(self):
        """Load categories from config and populate table."""
        self.table.setRowCount(0)

        categories = self.service.get_all_categories()

        for cat in categories:
            # Add main category row
            self._add_category_row(cat.name, "", cat.description, cat.budget)

            # Add subcategory rows
            for subcat in cat.subcategories:
                self._add_category_row(cat.name, subcat.name, subcat.description, None)

    def _add_category_row(self, category, subcategory, description, budget):
        """
        Add a row to the table.

        Args:
            category: Category name
            subcategory: Subcategory name or empty string
            description: Description text
            budget: Budget object or None
        """
        row = self.table.rowCount()
        self.table.insertRow(row)

        # Get palette for theme-aware colors
        app = QApplication.instance()
        palette = app.palette() if app else QPalette()

        # Category
        cat_item = QTableWidgetItem(category)
        if not subcategory:
            # Use theme-aware background for main categories
            cat_item.setBackground(Theme.color("header_bg"))
            font = cat_item.font()
            font.setBold(True)
            cat_item.setFont(font)
        self.table.setItem(row, 0, cat_item)

        # Subcategory
        subcat_item = QTableWidgetItem(subcategory)
        if subcategory:
            # Use palette color for subtle text instead of hardcoded gray
            subcat_item.setForeground(palette.color(QPalette.PlaceholderText))
        self.table.setItem(row, 1, subcat_item)

        # Description
        desc_item = QTableWidgetItem(description or "")
        self.table.setItem(row, 2, desc_item)

        # Budget
        budget_text = ""
        period_text = ""
        if budget:
            budget_text = f"${budget.amount:,.2f}"
            period_text = budget.period.value

        budget_item = QTableWidgetItem(budget_text)
        self.table.setItem(row, 3, budget_item)

        period_item = QTableWidgetItem(period_text)
        self.table.setItem(row, 4, period_item)

    def _on_selection_changed(self):
        """Handle selection change."""
        has_selection = len(self.table.selectedItems()) > 0
        self.add_subcat_btn.setEnabled(has_selection)
        self.set_budget_btn.setEnabled(has_selection)
        self.remove_btn.setEnabled(has_selection)

    def _on_add_category(self):
        """Handle add category button click."""
        name, ok = QInputDialog.getText(self, "Add Category", "Category name:")
        if not ok or not name.strip():
            return

        name = name.strip()

        # Get optional description
        description, ok = QInputDialog.getText(self, "Add Category", "Description (optional):")
        if not ok:
            return

        description = description.strip() if description else None

        try:
            self.service.add_category(name, description)
            self.service.save_categories()
            self._load_categories()
            self.categories_modified.emit()

            QMessageBox.information(self, "Success", f"Category '{name}' added successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add category:\n{str(e)}")

    def _on_add_subcategory(self):
        """Handle add subcategory button click."""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return

        # Get category name from selected row
        category_item = self.table.item(selected_row, 0)

        category_name = category_item.text()
        if not category_name:
            # User selected a subcategory row, need to find parent
            # Walk back to find category
            for row in range(selected_row - 1, -1, -1):
                item = self.table.item(row, 0)
                if item and item.text():
                    category_name = item.text()
                    break

        if not category_name:
            QMessageBox.warning(self, "Warning", "Could not determine parent category")
            return

        # Get subcategory name
        name, ok = QInputDialog.getText(
            self, "Add Subcategory", f"Subcategory name for '{category_name}':"
        )
        if not ok or not name.strip():
            return

        name = name.strip()

        # Get optional description
        description, ok = QInputDialog.getText(self, "Add Subcategory", "Description (optional):")
        if not ok:
            return

        description = description.strip() if description else None

        try:
            self.service.add_subcategory(category_name, name, description)
            self.service.save_categories()
            self._load_categories()
            self.categories_modified.emit()

            QMessageBox.information(
                self,
                "Success",
                f"Subcategory '{name}' added to '{category_name}' successfully",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to add subcategory:\n{str(e)}")

    def _on_set_budget(self):
        """Handle set budget button click."""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return

        # Get category name
        category_item = self.table.item(selected_row, 0)
        subcategory_item = self.table.item(selected_row, 1)

        category_name = category_item.text()
        if not category_name:
            # Walk back to find category
            for row in range(selected_row - 1, -1, -1):
                item = self.table.item(row, 0)
                if item and item.text():
                    category_name = item.text()
                    break

        subcategory_name = subcategory_item.text() if subcategory_item else ""

        if subcategory_name:
            QMessageBox.information(
                self,
                "Info",
                "Budgets can only be set on main categories, not subcategories.",
            )
            return

        if not category_name:
            return

        # Get current budget
        category = self.service.find_category(category_name)
        current_amount = category.budget.amount if category and category.budget else 0.0
        current_period = (
            category.budget.period if category and category.budget else BudgetPeriod.monthly
        )

        # Get new budget amount
        amount, ok = QInputDialog.getDouble(
            self,
            "Set Budget",
            f"Budget amount for '{category_name}':",
            current_amount,
            0.0,
            1000000.0,
            2,
        )
        if not ok:
            return

        # Get period
        period, ok = QInputDialog.getItem(
            self,
            "Set Budget",
            "Budget period:",
            ["monthly", "yearly"],
            0 if current_period == BudgetPeriod.monthly else 1,
            False,
        )
        if not ok:
            return

        budget_period = BudgetPeriod.monthly if period == "monthly" else BudgetPeriod.yearly

        try:
            self.service.update_category(
                category_name, budget_amount=amount, budget_period=budget_period
            )
            self.service.save_categories()
            self._load_categories()
            self.categories_modified.emit()

            QMessageBox.information(
                self,
                "Success",
                f"Budget for '{category_name}' set to ${amount:,.2f} per {period}",
            )
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to set budget:\n{str(e)}")

    def _on_remove(self):
        """Handle remove button click."""
        selected_row = self.table.currentRow()
        if selected_row < 0:
            return

        category_item = self.table.item(selected_row, 0)
        subcategory_item = self.table.item(selected_row, 1)

        category_name = category_item.text()
        if not category_name:
            # Walk back to find category
            for row in range(selected_row - 1, -1, -1):
                item = self.table.item(row, 0)
                if item and item.text():
                    category_name = item.text()
                    break

        subcategory_name = subcategory_item.text() if subcategory_item else ""

        if not category_name:
            return

        # Confirm removal
        if subcategory_name:
            msg = f"Remove subcategory '{subcategory_name}' from '{category_name}'?"
        else:
            msg = f"Remove category '{category_name}' and all its subcategories?"

        reply = QMessageBox.question(self, "Confirm Removal", msg, QMessageBox.Yes | QMessageBox.No)

        if reply != QMessageBox.Yes:
            return

        try:
            if subcategory_name:
                self.service.remove_subcategory(category_name, subcategory_name)
            else:
                self.service.remove_category(category_name)

            self.service.save_categories()
            self._load_categories()
            self.categories_modified.emit()

            QMessageBox.information(self, "Success", "Removed successfully")
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Failed to remove:\n{str(e)}")
