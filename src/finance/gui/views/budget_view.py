from __future__ import annotations

"""
Budget View - View for tracking budget vs actual spending

Shows budget comparison with color-coded indicators and summary statistics.
"""

from pathlib import Path
from datetime import date

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QHeaderView,
    QComboBox,
    QSpinBox,
    QGroupBox,
    QApplication,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QFont, QPalette

from finance.services.budget_service import BudgetService
from finance.gui.theme import Theme


class BudgetView(QWidget):
    """View for budget tracking."""

    def __init__(self, data_dir: Path, categories_config: Path, parent=None):
        super().__init__(parent)

        self.data_dir = data_dir
        self.categories_config = categories_config
        self.service = BudgetService(data_dir, categories_config)

        self._init_ui()
        self._load_budget()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("<h2>Budget Tracking</h2>")
        layout.addWidget(title)

        # Period selector
        period_layout = self._create_period_selector()
        layout.addLayout(period_layout)

        # Budget table
        self.table = QTableWidget()
        self.table.setColumnCount(6)
        self.table.setHorizontalHeaderLabels([
            "Category",
            "Subcategory",
            "Budget",
            "Actual",
            "Remaining",
            "% Used",
        ])
        self.table.setAlternatingRowColors(True)
        self.table.setSelectionBehavior(QTableWidget.SelectRows)
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)

        # Configure header - make columns resizable
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(False)

        # Set initial default widths
        header.resizeSection(0, 200)  # Category
        header.resizeSection(1, 150)  # Subcategory
        header.resizeSection(2, 120)  # Budget
        header.resizeSection(3, 120)  # Actual
        header.resizeSection(4, 120)  # Remaining
        header.resizeSection(5, 100)  # % Used

        layout.addWidget(self.table)

        # Summary section
        self.summary_label = QLabel()
        # Use theme-aware background color
        self.summary_label.setStyleSheet(
            f"padding: 10px; border-radius: 4px; border: 1px solid {Theme.color('border').name()};"
        )
        layout.addWidget(self.summary_label)

        # Info label
        info = QLabel(
            "<i>Budgets are automatically prorated: monthly reports use monthly budgets "
            "or divide yearly budgets by 12; yearly reports use yearly budgets or multiply "
            "monthly budgets by 12.</i>"
        )
        info.setWordWrap(True)
        info.setStyleSheet(f"color: {Theme.color('text_secondary').name()}; padding: 8px;")
        layout.addWidget(info)

    def _create_period_selector(self) -> QHBoxLayout:
        """Create the period selector controls."""
        layout = QHBoxLayout()

        layout.addWidget(QLabel("Period:"))

        # Year selector
        layout.addWidget(QLabel("Year:"))
        self.year_spin = QSpinBox()
        self.year_spin.setRange(2000, 2100)
        self.year_spin.setValue(date.today().year)
        self.year_spin.valueChanged.connect(self._on_period_changed)
        layout.addWidget(self.year_spin)

        # Month selector
        layout.addWidget(QLabel("Month:"))
        self.month_combo = QComboBox()
        self.month_combo.addItem("All Months", None)
        months = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ]
        for i, month_name in enumerate(months, 1):
            self.month_combo.addItem(month_name, i)

        self.month_combo.currentIndexChanged.connect(self._on_period_changed)
        layout.addWidget(self.month_combo)

        layout.addSpacing(20)

        # Refresh button
        self.refresh_btn = QPushButton("Refresh")
        self.refresh_btn.clicked.connect(self._load_budget)
        layout.addWidget(self.refresh_btn)

        layout.addStretch()

        return layout

    def _on_period_changed(self):
        """Handle period selection change."""
        self._load_budget()

    def _load_budget(self):
        """Load and display budget data."""
        self.table.setRowCount(0)

        # Get selected period
        year = self.year_spin.value()
        month = self.month_combo.currentData()

        # Get budget summary
        summary = self.service.get_budget_summary(year=year, month=month)

        # Get palette for theme-aware colors
        app = QApplication.instance()
        palette = app.palette() if app else QPalette()

        # Populate table
        for item in summary.items:
            row = self.table.rowCount()
            self.table.insertRow(row)

            # Category
            cat_item = QTableWidgetItem(item.category_name if item.is_category_header else "")
            if item.is_category_header:
                font = cat_item.font()
                font.setBold(True)
                cat_item.setFont(font)
                # Use theme-aware subtle background for main categories
                cat_item.setBackground(Theme.color("header_bg"))
            self.table.setItem(row, 0, cat_item)

            # Subcategory
            subcat_text = f"  {item.subcategory_name}" if item.subcategory_name else ""
            subcat_item = QTableWidgetItem(subcat_text)
            if item.subcategory_name:
                # Use palette color for subtle text instead of hardcoded gray
                subcat_item.setForeground(Theme.color("neutral_fg"))
            self.table.setItem(row, 1, subcat_item)

            # Budget
            budget_text = f"${item.budget_amount:,.2f}" if item.budget_amount else "—"
            budget_item = QTableWidgetItem(budget_text)
            budget_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self.table.setItem(row, 2, budget_item)

            # Actual
            actual_text = f"${item.actual_amount:,.2f}" if item.actual_amount > 0 else "—"
            actual_item = QTableWidgetItem(actual_text)
            actual_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
            if item.is_category_header:
                font = actual_item.font()
                font.setBold(True)
                actual_item.setFont(font)
            self.table.setItem(row, 3, actual_item)

            # Remaining
            if item.remaining is not None:
                if item.remaining >= 0:
                    remaining_text = f"${item.remaining:,.2f}"
                    remaining_color = Theme.color("positive_fg")
                else:
                    remaining_text = f"-${abs(item.remaining):,.2f}"
                    remaining_color = Theme.color("negative_fg")

                remaining_item = QTableWidgetItem(remaining_text)
                remaining_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)
                remaining_item.setForeground(remaining_color)
                self.table.setItem(row, 4, remaining_item)
            else:
                self.table.setItem(row, 4, QTableWidgetItem("—"))

            # % Used
            if item.percent_used is not None:
                pct_text = f"{item.percent_used:.1f}%"
                pct_item = QTableWidgetItem(pct_text)
                pct_item.setTextAlignment(Qt.AlignRight | Qt.AlignVCenter)

                # Color code based on percentage
                if item.percent_used > 100:
                    pct_color = Theme.color("negative_fg")
                    font = pct_item.font()
                    font.setBold(True)
                    pct_item.setFont(font)
                elif item.percent_used > 90:
                    pct_color = Theme.color("warning_fg")
                else:
                    pct_color = Theme.color("positive_fg")

                pct_item.setForeground(pct_color)
                self.table.setItem(row, 5, pct_item)
            else:
                self.table.setItem(row, 5, QTableWidgetItem("—"))

        # Update summary
        self._update_summary(summary)

    def _update_summary(self, summary):
        """Update the summary label."""
        if summary.total_remaining >= 0:
            remaining_text = f'<span style="color: {Theme.color("positive_fg").name()};">${summary.total_remaining:,.2f}</span>'
            remaining_label = "Remaining"
        else:
            remaining_text = f'<span style="color: {Theme.color("negative_fg").name()};">${abs(summary.total_remaining):,.2f}</span>'
            remaining_label = "Over Budget"

        summary_html = f"""
        <table width="100%">
        <tr>
            <td><b>Total Budgeted:</b> ${summary.total_budgeted:,.2f}</td>
            <td><b>Total Actual:</b> ${summary.total_actual:,.2f}</td>
            <td><b>{remaining_label}:</b> {remaining_text}</td>
            <td><b>% Used:</b> {summary.percent_used:.1f}%</td>
        </tr>
        </table>
        """

        if summary.over_budget_count > 0:
            plural = "y" if summary.over_budget_count == 1 else "ies"
            summary_html += f'<p style="color: {Theme.color("warning_fg").name()}; margin-top: 8px;">⚠ {summary.over_budget_count} categor{plural} over budget</p>'

        self.summary_label.setText(summary_html)

    def reload_budget(self):
        """Reload budget data (called externally)."""
        self._load_budget()
