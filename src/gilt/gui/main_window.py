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

from gilt.gui.views.dashboard_view import DashboardView
from gilt.gui.views.transactions_view import TransactionsView
from gilt.gui.views.categories_view import CategoriesView
from gilt.gui.views.budget_view import BudgetView
from gilt.gui.views.import_wizard import ImportWizard
from gilt.gui.dialogs.settings_dialog import SettingsDialog
from gilt.gui.services.import_service import ImportService
from gilt.services.event_sourcing_service import EventSourcingService
from gilt.storage.event_store import EventStore
from gilt.transfer.duplicate_detector import DuplicateDetector
from gilt.services.duplicate_service import DuplicateService
from gilt.services.smart_category_service import SmartCategoryService
from gilt.ml.categorization_classifier import CategorizationClassifier
from gilt.workspace import Workspace
from gilt.gui.theme import Theme


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Finance")
        self.setMinimumSize(1200, 800)

        # Get data directory and config paths from settings
        self.data_dir = SettingsDialog.get_data_dir()
        self.categories_config = SettingsDialog.get_categories_config()
        self.workspace = Workspace(root=self.data_dir)

        self._init_services()
        self._init_ui()
        self._create_menu_bar()
        self._create_toolbar()
        self._create_status_bar()

        # Show transactions view by default
        self.nav_list.setCurrentRow(0)

    def _init_services(self):
        """Initialize application services."""
        # Event Store
        self.event_store = EventStore(str(self.workspace.event_store_path))

        # Duplicate Detection
        self.duplicate_detector = DuplicateDetector(event_store_path=self.workspace.event_store_path)
        self.duplicate_service = DuplicateService(self.duplicate_detector, self.event_store)

        # Smart Categorization
        self.categorization_classifier = CategorizationClassifier(self.event_store)
        self.smart_category_service = SmartCategoryService(self.categorization_classifier, self.event_store)

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
        Apply theme to navigation widget.

        Args:
            theme: 'light' or 'dark'
        """
        style = Theme.get_nav_style()

        self.nav_widget.setStyleSheet(
            f"""
            QWidget {{
                background-color: {style['bg']};
            }}
            QListWidget {{
                background-color: {style['item_bg']};
                color: {style['text']};
                border: none;
                font-size: 14pt;
                outline: none;
            }}
            QListWidget::item {{
                padding: 15px;
                border-bottom: 1px solid {style['border']};
            }}
            QListWidget::item:selected {{
                background-color: {style['selected']};
            }}
            QListWidget::item:hover {{
                background-color: {style['hover']};
            }}
        """
        )

        self.nav_title.setStyleSheet(
            f"""
            QLabel {{
                background-color: {style['title_bg']};
                color: {style['text']};
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
        self.transactions_view = TransactionsView(
            self.data_dir,
            duplicate_service=self.duplicate_service,
            smart_category_service=self.smart_category_service,
            parent=self
        )
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

    def _create_toolbar(self):
        """Create the main toolbar."""
        toolbar = self.addToolBar("Main Toolbar")
        toolbar.setMovable(False)
        toolbar.setIconSize(QSize(16, 16))
        toolbar.setToolButtonStyle(Qt.ToolButtonTextBesideIcon)

        # Import Action
        import_action = QAction("Import Data", self)
        import_action.setStatusTip("Import CSV files from banks")
        import_action.triggered.connect(self._show_import_wizard)
        toolbar.addAction(import_action)

        toolbar.addSeparator()

        # Refresh Action
        refresh_action = QAction("Refresh", self)
        refresh_action.setStatusTip("Refresh current view")
        refresh_action.triggered.connect(self._refresh_current_view)
        toolbar.addAction(refresh_action)

    def _create_status_bar(self):
        """Create the status bar."""
        self.statusBar().showMessage("Ready")

    def _show_import_wizard(self):
        """Show the import wizard."""
        # Get accounts config path
        accounts_config = SettingsDialog.get_accounts_config()

        # Initialize services
        es_service = EventSourcingService(workspace=self.workspace)
        event_store = es_service.get_event_store()

        detector = DuplicateDetector(
            event_store_path=self.workspace.event_store_path,
            use_ml=True
        )
        duplicate_service = DuplicateService(detector, event_store)

        # Initialize smart category service
        classifier = CategorizationClassifier(event_store)
        smart_category_service = SmartCategoryService(classifier, event_store)

        # Create import service with duplicate service and event sourcing service
        import_service = ImportService(
            self.data_dir,
            accounts_config,
            duplicate_service=duplicate_service,
            event_sourcing_service=es_service,
            smart_category_service=smart_category_service
        )

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
            self.workspace = Workspace(root=self.data_dir)
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
