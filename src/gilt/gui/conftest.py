from __future__ import annotations

"""Session-scoped QApplication fixture for GUI specs running headlessly."""

import os

import pytest


@pytest.fixture(scope="session")
def qapp():
    """Session-scoped QApplication in offscreen mode for headless GUI tests."""
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    app = QApplication.instance() or QApplication([])
    yield app
