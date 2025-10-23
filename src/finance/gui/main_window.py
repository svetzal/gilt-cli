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

from finance.gui.views.transactions_view import TransactionsView
from finance.gui.dialogs.settings_dialog import SettingsDialog


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self):
        super().__init__()

        self.setWindowTitle("Finance Local")
        self.setMinimumSize(1200, 800)

        # Get data directory from settings
        self.data_dir = SettingsDialog.get_data_dir()

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
        self.nav_title = QLabel("Finance Local")
        self.nav_title.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.nav_title)

        # Navigation list
        self.nav_list = QListWidget()
        self.nav_list.setIconSize(QSize(24, 24))

        # Add navigation items
        self.nav_list.addItem(self._create_nav_item("💰 Transactions"))
        self.nav_list.addItem(self._create_nav_item("⚙️  Settings"))

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
        # Transactions view
        self.transactions_view = TransactionsView(self.data_dir, self)
        self.content_stack.addWidget(self.transactions_view)

        # Settings placeholder (we'll show dialog instead)
        settings_placeholder = QLabel("Settings\n\n(Use File → Settings)")
        settings_placeholder.setAlignment(Qt.AlignCenter)
        settings_placeholder.setStyleSheet("font-size: 16pt; color: gray;")
        self.content_stack.addWidget(settings_placeholder)

    def _on_nav_changed(self, index: int):
        """Handle navigation item change."""
        if index == 0:  # Transactions
            self.content_stack.setCurrentIndex(0)
        elif index == 1:  # Settings
            # Show settings dialog instead of switching view
            self._show_settings()
            # Revert selection to previous view
            self.nav_list.setCurrentRow(0)

    def _create_menu_bar(self):
        """Create the menu bar."""
        menubar = self.menuBar()

        # File menu
        file_menu = menubar.addMenu("&File")

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

        about_action = QAction("&About Finance Local", self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

    def _create_status_bar(self):
        """Create the status bar."""
        self.statusBar().showMessage("Ready")

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
        if current_index == 0:  # Transactions view
            self.transactions_view.reload_transactions()
            self.statusBar().showMessage("Transactions reloaded", 3000)

    def _show_about(self):
        """Show about dialog."""
        from PySide6.QtWidgets import QMessageBox

        QMessageBox.about(
            self,
            "About Finance Local",
            "<h2>Finance Local</h2>"
            "<p>Version 0.0.0</p>"
            "<p>A <b>local-only, privacy-first</b> financial management tool.</p>"
            "<p>All data processing happens on your machine with no network I/O.</p>"
            "<p><small>Built with Python and Qt6</small></p>",
        )
