from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication


class Theme:
    """Centralized theme management for colors."""

    @staticmethod
    def is_dark() -> bool:
        """Check if dark mode is active."""
        app = QApplication.instance()
        if app:
            return app.property("current_theme") == "dark"
        return False

    @staticmethod
    def color(name: str) -> QColor:
        """Get color by name for current theme."""
        is_dark = Theme.is_dark()

        # Tuple format: (Light Mode, Dark Mode)
        colors = {
            # Backgrounds
            "success_bg": ("#e6fffa", "#0d3329"),  # Light teal / Dark teal
            "warning_bg": ("#fff5f5", "#4a1818"),  # Light red / Dark red
            "header_bg": ("#f0f0f0", "#2d2d2d"),  # Light gray / Dark gray
            "highlight_bg": ("#fff3cd", "#4d4d00"),  # Light yellow / Dark yellow
            # Foregrounds (Text)
            "success_fg": ("#2c3e50", "#e0e0e0"),  # Dark blue / Light gray
            "warning_fg": ("#2c3e50", "#e0e0e0"),
            "header_fg": ("#000000", "#ffffff"),
            # Semantic Text
            "positive_fg": ("#27ae60", "#2ecc71"),  # Green / Brighter green
            "negative_fg": ("#e74c3c", "#ff6b6b"),  # Red / Brighter red
            "neutral_fg": ("#95a5a6", "#bdc3c7"),  # Gray
            "link_fg": ("#3498db", "#5dade2"),  # Blue
            "text_primary": ("#000000", "#ffffff"),  # Black / White
            "text_secondary": ("#666666", "#b0b0b0"),  # Dark Gray / Light Gray
            "border": ("#dcdcdc", "#404040"),  # Light Gray / Dark Gray
        }

        if name in colors:
            light, dark = colors[name]
            return QColor(dark if is_dark else light)

        return QColor("#000000")

    @staticmethod
    def get_nav_style() -> dict:
        """Get navigation sidebar style colors."""
        if Theme.is_dark():
            return {
                "bg": "#1e1e1e",
                "item_bg": "#1e1e1e",
                "border": "#2e2e2e",
                "selected": "#0d7377",
                "hover": "#2e2e2e",
                "text": "#e0e0e0",
                "title_bg": "#0a0a0a",
            }
        else:
            return {
                "bg": "#2c3e50",
                "item_bg": "#2c3e50",
                "border": "#34495e",
                "selected": "#3498db",
                "hover": "#34495e",
                "text": "white",
                "title_bg": "#1a252f",
            }
