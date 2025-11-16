from __future__ import annotations

"""
Dashboard View - Overview dashboard with key metrics

Shows summary cards and quick access to important information.
"""

from pathlib import Path
from datetime import date

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QGroupBox,
    QGridLayout,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QFont

from finance.gui.services.budget_service import BudgetService
from finance.gui.services.transaction_service import TransactionService


class SummaryCard(QGroupBox):
    """A summary card widget showing a metric."""

    def __init__(self, title: str, parent=None):
        super().__init__(parent)

        self.setTitle(title)
        self.setMinimumHeight(120)

        layout = QVBoxLayout(self)

        # Value label (large)
        self.value_label = QLabel("—")
        font = QFont()
        font.setPointSize(24)
        font.setBold(True)
        self.value_label.setFont(font)
        self.value_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.value_label)

        # Subtitle label (smaller)
        self.subtitle_label = QLabel("")
        self.subtitle_label.setAlignment(Qt.AlignCenter)
        self.subtitle_label.setStyleSheet("color: gray;")
        layout.addWidget(self.subtitle_label)

        layout.addStretch()

    def set_value(self, value: str):
        """Set the main value."""
        self.value_label.setText(value)

    def set_subtitle(self, subtitle: str):
        """Set the subtitle text."""
        self.subtitle_label.setText(subtitle)

    def set_value_color(self, color: str):
        """Set the color of the value text."""
        self.value_label.setStyleSheet(f"color: {color};")


class DashboardView(QWidget):
    """Dashboard overview."""

    # Signal to navigate to other views
    navigate_to = Signal(int)  # Index of view to navigate to

    def __init__(self, data_dir: Path, categories_config: Path, parent=None):
        super().__init__(parent)

        self.data_dir = data_dir
        self.categories_config = categories_config
        self.budget_service = BudgetService(data_dir, categories_config)
        self.transaction_service = TransactionService(data_dir)

        self._init_ui()
        self._load_dashboard()

    def _init_ui(self):
        """Initialize the user interface."""
        layout = QVBoxLayout(self)

        # Title
        title = QLabel("<h1>Dashboard</h1>")
        layout.addWidget(title)

        # Summary cards in a grid
        cards_layout = QGridLayout()

        # Card 1: This Month's Spending
        self.spending_card = SummaryCard("This Month's Spending")
        cards_layout.addWidget(self.spending_card, 0, 0)

        # Card 2: Budget Status
        self.budget_card = SummaryCard("Budget Status")
        cards_layout.addWidget(self.budget_card, 0, 1)

        # Card 3: Uncategorized Transactions
        self.uncategorized_card = SummaryCard("Uncategorized")
        cards_layout.addWidget(self.uncategorized_card, 1, 0)

        # Card 4: Total Transactions (YTD)
        self.total_card = SummaryCard("Year to Date")
        cards_layout.addWidget(self.total_card, 1, 1)

        layout.addLayout(cards_layout)

        # Quick actions
        actions_group = QGroupBox("Quick Actions")
        actions_layout = QHBoxLayout(actions_group)

        view_budget_btn = QPushButton("View Budget")
        view_budget_btn.clicked.connect(lambda: self.navigate_to.emit(2))  # Budget view index
        actions_layout.addWidget(view_budget_btn)

        view_transactions_btn = QPushButton("View Transactions")
        view_transactions_btn.clicked.connect(lambda: self.navigate_to.emit(0))  # Transactions view index
        actions_layout.addWidget(view_transactions_btn)

        view_categories_btn = QPushButton("Manage Categories")
        view_categories_btn.clicked.connect(lambda: self.navigate_to.emit(1))  # Categories view index
        actions_layout.addWidget(view_categories_btn)

        actions_layout.addStretch()

        # Refresh button
        refresh_btn = QPushButton("Refresh Dashboard")
        refresh_btn.clicked.connect(self._load_dashboard)
        actions_layout.addWidget(refresh_btn)

        layout.addWidget(actions_group)

        layout.addStretch()

        # Info
        info = QLabel(
            "<i>Dashboard shows current month and year-to-date metrics. "
            "Click refresh to update with latest data.</i>"
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; padding: 8px;")
        layout.addWidget(info)

    def _load_dashboard(self):
        """Load and display dashboard metrics."""
        today = date.today()
        current_year = today.year
        current_month = today.month

        # Get this month's spending
        month_spending = self.budget_service.get_total_spending(
            year=current_year, month=current_month
        )
        self.spending_card.set_value(f"${month_spending:,.2f}")
        month_name = date(current_year, current_month, 1).strftime("%B")
        self.spending_card.set_subtitle(f"{month_name} {current_year}")

        # Get budget status for this month
        budget_summary = self.budget_service.get_budget_summary(
            year=current_year, month=current_month
        )

        if budget_summary.total_budgeted > 0:
            pct_used = budget_summary.percent_used
            self.budget_card.set_value(f"{pct_used:.1f}%")

            if pct_used > 100:
                self.budget_card.set_subtitle(
                    f"${abs(budget_summary.total_remaining):,.2f} over budget"
                )
                self.budget_card.set_value_color("red")
            elif pct_used > 90:
                self.budget_card.set_subtitle(
                    f"${budget_summary.total_remaining:,.2f} remaining"
                )
                self.budget_card.set_value_color("orange")
            else:
                self.budget_card.set_subtitle(
                    f"${budget_summary.total_remaining:,.2f} remaining"
                )
                self.budget_card.set_value_color("green")
        else:
            self.budget_card.set_value("—")
            self.budget_card.set_subtitle("No budgets set")

        # Get uncategorized count
        uncategorized_count = self.budget_service.get_uncategorized_count()
        self.uncategorized_card.set_value(str(uncategorized_count))
        if uncategorized_count > 0:
            self.uncategorized_card.set_subtitle("transactions need categorization")
            self.uncategorized_card.set_value_color("orange")
        else:
            self.uncategorized_card.set_subtitle("all categorized!")
            self.uncategorized_card.set_value_color("green")

        # Get YTD spending
        ytd_spending = self.budget_service.get_total_spending(year=current_year)
        self.total_card.set_value(f"${ytd_spending:,.2f}")
        self.total_card.set_subtitle(f"Total spending in {current_year}")

    def reload_dashboard(self):
        """Reload dashboard data (called externally)."""
        self._load_dashboard()
