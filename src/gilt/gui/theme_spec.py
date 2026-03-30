from __future__ import annotations

"""
Specifications for Theme utility — centralized color and style management.
"""

import pytest

pytest.importorskip("PySide6")

from unittest.mock import MagicMock, patch

from PySide6.QtGui import QColor

from gilt.gui.theme import Theme


class DescribeThemeIsDark:
    """Behaviour of Theme.is_dark() dark mode detection."""

    def it_should_return_false_when_no_application_instance(self):
        with patch("gilt.gui.theme.QApplication") as mock_app_cls:
            mock_app_cls.instance.return_value = None
            assert Theme.is_dark() is False

    def it_should_return_false_when_app_property_is_not_dark(self):
        mock_app = MagicMock()
        mock_app.property.return_value = "light"
        with patch("gilt.gui.theme.QApplication") as mock_app_cls:
            mock_app_cls.instance.return_value = mock_app
            assert Theme.is_dark() is False

    def it_should_return_true_when_app_property_is_dark(self):
        mock_app = MagicMock()
        mock_app.property.return_value = "dark"
        with patch("gilt.gui.theme.QApplication") as mock_app_cls:
            mock_app_cls.instance.return_value = mock_app
            assert Theme.is_dark() is True

    def it_should_check_current_theme_property_on_app_instance(self):
        mock_app = MagicMock()
        mock_app.property.return_value = "light"
        with patch("gilt.gui.theme.QApplication") as mock_app_cls:
            mock_app_cls.instance.return_value = mock_app
            Theme.is_dark()
            mock_app.property.assert_called_once_with("current_theme")


class DescribeThemeColor:
    """Behaviour of Theme.color() returning correct QColor for each theme."""

    def it_should_return_light_color_when_not_dark(self):
        with patch.object(Theme, "is_dark", return_value=False):
            color = Theme.color("positive_fg")
            assert color.name() == "#27ae60"

    def it_should_return_dark_color_when_dark(self):
        with patch.object(Theme, "is_dark", return_value=True):
            color = Theme.color("positive_fg")
            assert color.name() == "#2ecc71"

    def it_should_return_light_negative_color_in_light_mode(self):
        with patch.object(Theme, "is_dark", return_value=False):
            color = Theme.color("negative_fg")
            assert color.name() == "#e74c3c"

    def it_should_return_dark_negative_color_in_dark_mode(self):
        with patch.object(Theme, "is_dark", return_value=True):
            color = Theme.color("negative_fg")
            assert color.name() == "#ff6b6b"

    def it_should_return_black_for_unknown_color_name(self):
        with patch.object(Theme, "is_dark", return_value=False):
            color = Theme.color("nonexistent_color")
            assert color.name() == "#000000"

    def it_should_return_qcolor_instance(self):
        with patch.object(Theme, "is_dark", return_value=False):
            color = Theme.color("border")
            assert isinstance(color, QColor)

    def it_should_return_light_header_bg_in_light_mode(self):
        with patch.object(Theme, "is_dark", return_value=False):
            color = Theme.color("header_bg")
            assert color.name() == "#f0f0f0"

    def it_should_return_dark_header_bg_in_dark_mode(self):
        with patch.object(Theme, "is_dark", return_value=True):
            color = Theme.color("header_bg")
            assert color.name() == "#2d2d2d"


class DescribeThemeGetNavStyle:
    """Behaviour of Theme.get_nav_style() returning theme-aware style dicts."""

    def it_should_return_dict_with_required_keys(self):
        with patch.object(Theme, "is_dark", return_value=False):
            style = Theme.get_nav_style()
        required_keys = {"bg", "item_bg", "border", "selected", "hover", "text", "title_bg"}
        assert required_keys.issubset(style.keys())

    def it_should_return_light_nav_style_when_not_dark(self):
        with patch.object(Theme, "is_dark", return_value=False):
            style = Theme.get_nav_style()
        assert style["bg"] == "#2c3e50"
        assert style["selected"] == "#3498db"
        assert style["text"] == "white"

    def it_should_return_dark_nav_style_when_dark(self):
        with patch.object(Theme, "is_dark", return_value=True):
            style = Theme.get_nav_style()
        assert style["bg"] == "#1e1e1e"
        assert style["selected"] == "#0d7377"
        assert style["text"] == "#e0e0e0"

    def it_should_return_different_border_for_light_vs_dark(self):
        with patch.object(Theme, "is_dark", return_value=False):
            light_style = Theme.get_nav_style()
        with patch.object(Theme, "is_dark", return_value=True):
            dark_style = Theme.get_nav_style()
        assert light_style["border"] != dark_style["border"]
