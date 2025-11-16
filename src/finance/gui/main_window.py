from __future__ import annotations

"""
Main Window - Primary application window with navigation

Provides navigation sidebar and content area for different views.
"""

from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow,
    QWidget,
    QHBoxLayout,
    QVBoxLayout,
    QListWidget,
    QListWidgetItem,
    QStackedWidget,
    QLabel,
    QStatusBar,
    QMenuBar,
    QMenu,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QAction, QIcon

from finance.gui.views.dashboard_view import DashboardView
from finance.gui.views.transactions_view import TransactionsView
from finance.gui.views.categories_view import CategoriesView
from finance.gui.views.budget_view import BudgetView
from finance.gui.views.import_wizard import ImportWizard
from finance.gui.dialogs.settings_dialog import SettingsDialog
from finance.gui.services.import_service import ImportService


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Finance")
        self.setMinimumSize(1200, 800)

        # Get data directory and config paths from settings
        self.data_dir = SettingsDialog.get_data_dir()
        self.categories_config = SettingsDialog.get_categories_config()

        self._init_ui()
        self._create_menu_bar()
        self._create_status_bar()

        # Show transactions view by default
        self.nav_list.setCurrentRow(0)

    def showEvent(self, event):
        """Handle window show event to apply initial theme."""
        super().showEvent(event)
        # Apply theme based on current app property (set by app.py)
        from PySide6.QtWidgets import QApplication
        app = QApplication.instance()
        if app:
            theme = app.property("current_theme") or "light"
            self._apply_nav_theme(theme)

    def _init_ui(self):
        """Initialize the user interface."""
        # Central widget with horizontal layout
        central = QWidget()
        self.setCentralWidget(central)
        layout = QHBoxLayout(central)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        # Navigation sidebar
        nav_widget = self._create_navigation()
        layout.addWidget(nav_widget)

        # Content area (stacked widget for different views)
        self.content_stack = QStackedWidget()
        layout.addWidget(self.content_stack)

        # Create views
        self._create_views()

    def _create_navigation(self) -> QWidget:
        """Create the navigation sidebar."""
        self.nav_widget = QWidget()
        self.nav_widget.setMaximumWidth(200)

        layout = QVBoxLayout(self.nav_widget)
        layout.setContentsMargins(0, 0, 0, 0)

        # App title
        self.nav_title = QLabel("Finance")
        self.nav_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.nav_title)

        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setIconSize(QSize(24, 24))

        # Add navigation items (only for views, not dialogs)
        self.nav_list.addItem(self._create_nav_item("📊 Dashboard"))
        self.nav_list.addItem(self._create_nav_item("💰 Transactions"))
        self.nav_list.addItem(self._create_nav_item("📁 Categories"))
        self.nav_list.addItem(self._create_nav_item("📈 Budget"))

        self.nav_list.currentRowChanged.connect(self._on_nav_changed)

        layout.addWidget(self.nav_list)

        # Apply initial theme
        self._apply_nav_theme("light")  # Will be updated by app

        return self.nav_widget

    def _apply_nav_theme(self, theme: str):
        """
        Apply theme-specific styling to navigation sidebar.

        Args:
            theme: 'light' or 'dark'
        """
        if theme == "dark":
            nav_bg = "#1e1e1e"
            nav_item_bg = "#1e1e1e"
            nav_border = "#2e2e2e"
            nav_selected = "#0d7377"
            nav_hover = "#2e2e2e"
            nav_text = "#e0e0e0"
            title_bg = "#0a0a0a"
        else:
            nav_bg = "#2c3e50"
            nav_item_bg = "#2c3e50"
            nav_border = "#34495e"
            nav_selected = "#3498db"
            nav_hover = "#34495e"
            nav_text = "white"
            title_bg = "#1a252f"

        self.nav_widget.setStyleSheet(
            f"""
            QWidget {{
                background-color: {nav_bg};
            }}
            QListWidget {{
                background-color: {nav_item_bg};
                color: {nav_text};
                border: none;
                font-size: 14pt;
                outline: none;
            }}
            QListWidget::item {{
                padding: 15px;
                border-bottom: 1px solid {nav_border};
            }}
            QListWidget::item:selected {{
                background-color: {nav_selected};
            }}
            QListWidget::item:hover {{
                background-color: {nav_hover};
            }}
        """
        )

        self.nav_title.setStyleSheet(
            f"""
            QLabel {{
                background-color: {title_bg};
                color: {nav_text};
                font-size: 18pt;
                font-weight: bold;
                padding: 20px;
            }}
        """
        )

    def on_theme_changed(self, theme: str):
        """
        Handle theme change event.

        Args:
            theme: 'light' or 'dark'
        """
        self._apply_nav_theme(theme)

    def _create_nav_item(self, text: str) -> QListWidgetItem:
        """Create a navigation list item."""
        item = QListWidgetItem(text)
        item.setFlags(item.flags() & ~Qt.ItemIsEditable)
        return item

    def _create_views(self):
        """Create and add views to the content stack."""
        # Dashboard view (index 0)
        self.dashboard_view = DashboardView(self.data_dir, self.categories_config, self)
        self.dashboard_view.navigate_to.connect(self._on_navigate_to_view)
        self.content_stack.addWidget(self.dashboard_view)

        # Transactions view (index 1)
        self.transactions_view = TransactionsView(self.data_dir, self)
        self.content_stack.addWidget(self.transactions_view)

        # Categories view (index 2)
        self.categories_view = CategoriesView(self.categories_config, self)
        self.content_stack.addWidget(self.categories_view)

        # Budget view (index 3)
        self.budget_view = BudgetView(self.data_dir, self.categories_config, self)
        self.content_stack.addWidget(self.budget_view)

    def _on_nav_changed(self, index: int):
        """Handle navigation item change."""
        # Map navigation index to content stack index
        # Dialogs (Import, Settings) are accessed via menu
        if index == 0:  # Dashboard
            self.content_stack.setCurrentIndex(0)
        elif index == 1:  # Transactions
            self.content_stack.setCurrentIndex(1)
        elif index == 2:  # Categories
            self.content_stack.setCurrentIndex(2)
        elif index == 3:  # Budget
            self.content_stack.setCurrentIndex(3)

    def _on_navigate_to_view(self, view_index: int):
        """Handle navigation request from dashboard."""
        # Set both the content stack and navigation list
        self.content_stack.setCurrentIndex(view_index)
        self.nav_list.setCurrentRow(view_index)

    def _create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

        import_action = QAction("&Import CSV Files...", self)
        import_action.setShortcut("Ctrl+I")
        import_action.triggered.connect(self._show_import_wizard)
        file_menu.addAction(import_action)

        file_menu.addSeparator()

        settings_action = QAction("&Settings...", self)
        settings_action.setShortcut("Ctrl+,")
        settings_action.triggered.connect(self._show_settings)
        file_menu.addAction(settings_action)

        file_menu.addSeparator()

        quit_action = QAction("&Quit", self)
        quit_action.setShortcut("Ctrl+Q")
        quit_action.triggered.connect(self.close)
        file_menu.addAction(quit_action)

        # View menu
        view_menu = menubar.addMenu("&View")

        refresh_action = QAction("&Refresh", self)
        refresh_action.setShortcut("F5")
        refresh_action.triggered.connect(self._refresh_current_view)
        view_menu.addAction(refresh_action)

        # Help menu
        help_menu = menubar.addMenu("&Help")

        about_action = QAction("&About Finance", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_status_bar(self):
        """Create the status bar."""
        self.statusBar().showMessage("Ready")

    def _show_import_wizard(self):
        """Show the import wizard."""
        # Get accounts config path
        accounts_config = self.data_dir.parent / "config" / "accounts.yml"

        # Create import service
        import_service = ImportService(self.data_dir, accounts_config)

        # Show wizard
        wizard = ImportWizard(import_service, self)
        if wizard.exec():
            # Import completed, reload transactions
            self.transactions_view.reload_transactions()
            self.statusBar().showMessage("Import completed", 3000)

    def _show_settings(self):
        """Show the settings dialog."""
        dialog = SettingsDialog(self)
        if dialog.exec():
            # Settings changed, reload data directory
            self.data_dir = SettingsDialog.get_data_dir()
            self._refresh_current_view()
            self.statusBar().showMessage("Settings saved", 3000)

    def _refresh_current_view(self):
        """Refresh the current view."""
        current_index = self.content_stack.currentIndex()
        if current_index == 0:  # Dashboard view
            self.dashboard_view.reload_dashboard()
            self.statusBar().showMessage("Dashboard reloaded", 3000)
        elif current_index == 1:  # Transactions view
            self.transactions_view.reload_transactions()
            self.statusBar().showMessage("Transactions reloaded", 3000)
        elif current_index == 2:  # Categories view
            self.categories_view._load_categories()
            self.statusBar().showMessage("Categories reloaded", 3000)
        elif current_index == 3:  # Budget view
            self.budget_view.reload_budget()
            self.statusBar().showMessage("Budget reloaded", 3000)

    def _show_about(self):
        """Show about dialog."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            "About Finance",
            "<h2>Finance</h2>"
            "<p>Version 0.0.0</p>"
            "<p>A <b>local-only, privacy-first</b> financial management tool.</p>"
            "<p>All data processing happens on your machine with no network I/O.</p>"
            "<p><small>Built with Python and Qt6</small></p>",
        )
