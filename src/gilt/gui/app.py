from __future__ import annotations

"""
Gilt GUI Application

Privacy-first Qt6 graphical user interface for Gilt.
All data processing remains local-only with no network I/O.
"""

import sys
from pathlib import Path

from PySide6.QtGui import QPalette
from PySide6.QtWidgets import QApplication

from gilt.gui.main_window import MainWindow


def is_dark_mode(app: QApplication) -> bool:
    """
    Detect if the system is in dark mode.

    Args:
        app: QApplication instance

    Returns:
        True if dark mode is active, False otherwise
    """
    # Check the system palette
    palette = app.palette()
    window_color = palette.color(QPalette.Window)
    text_color = palette.color(QPalette.WindowText)

    # Dark mode: window is darker than text
    # Light mode: window is lighter than text
    window_luminance = (
        0.299 * window_color.red() + 0.587 * window_color.green() + 0.114 * window_color.blue()
    )
    text_luminance = (
        0.299 * text_color.red() + 0.587 * text_color.green() + 0.114 * text_color.blue()
    )

    return window_luminance < text_luminance


def load_stylesheet(theme: str) -> str:
    """
    Load stylesheet for the specified theme.

    Args:
        theme: 'light' or 'dark'

    Returns:
        Stylesheet content as string
    """
    resources_dir = Path(__file__).parent / "resources"
    stylesheet_path = resources_dir / f"styles_{theme}.qss"

    if stylesheet_path.exists():
        try:
            with open(stylesheet_path, encoding="utf-8") as f:
                return f.read()
        except Exception as e:
            print(f"Warning: Could not load {theme} stylesheet: {e}")

    # Fallback: minimal stylesheet that respects system colors
    return ""


def apply_stylesheet(app: QApplication):
    """
    Apply application stylesheet based on system theme.

    Args:
        app: QApplication instance
    """
    # Detect system theme
    theme = "dark" if is_dark_mode(app) else "light"

    # Load and apply stylesheet
    stylesheet = load_stylesheet(theme)
    app.setStyleSheet(stylesheet)

    # Store current theme for comparison
    app.setProperty("current_theme", theme)


class ThemeManager:
    """Manager for handling theme changes."""

    def __init__(self, app: QApplication):
        self.app = app
        self.windows = []

    def register_window(self, window):
        """Register a window to receive theme updates."""
        self.windows.append(window)

    def on_palette_changed(self):
        """Handle system palette change (theme switch)."""
        old_theme = self.app.property("current_theme")
        new_theme = "dark" if is_dark_mode(self.app) else "light"

        # Only update if theme actually changed
        if old_theme != new_theme:
            print(f"System theme changed: {old_theme} → {new_theme}")
            apply_stylesheet(self.app)

            # Notify all windows to update their custom styling
            for window in self.windows:
                if hasattr(window, "on_theme_changed"):
                    window.on_theme_changed(new_theme)


def main():
    """Main entry point for the GUI application."""
    # Create application
    app = QApplication(sys.argv)

    # Set application metadata
    app.setApplicationName("Gilt")
    app.setOrganizationName("Mojility")
    app.setOrganizationDomain("mojility.com")

    # Create theme manager
    theme_manager = ThemeManager(app)

    # Apply initial stylesheet based on system theme
    apply_stylesheet(app)

    # Create and show main window
    window = MainWindow()
    theme_manager.register_window(window)
    window.show()

    # Connect to palette changes (theme switches)
    app.paletteChanged.connect(theme_manager.on_palette_changed)

    # Run event loop
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
