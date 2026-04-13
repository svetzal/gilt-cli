from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

try:
    from PySide6.QtGui import QPalette
    from PySide6.QtWidgets import QApplication

    _app = QApplication.instance() or QApplication([])
    from gilt.gui.app import ThemeManager, is_dark_mode, load_stylesheet

    HAS_QT = True
except ImportError:
    HAS_QT = False

pytestmark = pytest.mark.skipif(not HAS_QT, reason="PySide6 not installed")


def _make_mock_app(window_rgb: tuple, text_rgb: tuple) -> MagicMock:
    """Build a mock QApplication whose palette returns the given RGB colors."""

    def make_color(r: int, g: int, b: int) -> MagicMock:
        color = MagicMock()
        color.red.return_value = r
        color.green.return_value = g
        color.blue.return_value = b
        return color

    palette = MagicMock()
    palette.color.side_effect = lambda role: (
        make_color(*window_rgb) if role == QPalette.Window else make_color(*text_rgb)
    )
    app = MagicMock()
    app.palette.return_value = palette
    return app


class DescribeIsDarkMode:
    def it_should_return_true_when_window_is_darker_than_text(self):
        mock_app = _make_mock_app(window_rgb=(10, 10, 10), text_rgb=(200, 200, 200))
        assert is_dark_mode(mock_app) is True

    def it_should_return_false_when_window_is_lighter_than_text(self):
        mock_app = _make_mock_app(window_rgb=(200, 200, 200), text_rgb=(10, 10, 10))
        assert is_dark_mode(mock_app) is False


class DescribeLoadStylesheet:
    def it_should_return_empty_string_for_nonexistent_theme(self):
        result = load_stylesheet("nonexistent_theme_xyz")
        assert result == ""


class DescribeThemeManager:
    def it_should_not_apply_stylesheet_when_theme_is_unchanged(self):
        mock_app = MagicMock()
        mock_app.property.return_value = "dark"
        manager = ThemeManager(mock_app)

        with (
            patch("gilt.gui.app.is_dark_mode", return_value=True),
            patch("gilt.gui.app.apply_stylesheet") as mock_apply,
        ):
            manager.on_palette_changed()
            mock_apply.assert_not_called()

    def it_should_apply_stylesheet_when_theme_changes(self):
        mock_app = MagicMock()
        mock_app.property.return_value = "light"
        manager = ThemeManager(mock_app)

        with (
            patch("gilt.gui.app.is_dark_mode", return_value=True),
            patch("gilt.gui.app.apply_stylesheet") as mock_apply,
        ):
            manager.on_palette_changed()
            mock_apply.assert_called_once_with(mock_app)

    def it_should_notify_registered_windows_when_theme_changes(self):
        mock_app = MagicMock()
        mock_app.property.return_value = "light"
        manager = ThemeManager(mock_app)

        mock_window = MagicMock()
        manager.register_window(mock_window)

        with (
            patch("gilt.gui.app.is_dark_mode", return_value=True),
            patch("gilt.gui.app.apply_stylesheet"),
        ):
            manager.on_palette_changed()
            mock_window.on_theme_changed.assert_called_once_with("dark")

    def it_should_not_notify_windows_when_theme_is_unchanged(self):
        mock_app = MagicMock()
        mock_app.property.return_value = "dark"
        manager = ThemeManager(mock_app)

        mock_window = MagicMock()
        manager.register_window(mock_window)

        with (
            patch("gilt.gui.app.is_dark_mode", return_value=True),
            patch("gilt.gui.app.apply_stylesheet"),
        ):
            manager.on_palette_changed()
            mock_window.on_theme_changed.assert_not_called()
