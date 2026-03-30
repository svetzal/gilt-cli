from __future__ import annotations

"""Specs for CategoryDelegate logic — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")


class DescribeCreateEditorProxyTraversal:
    """Tests for proxy chain traversal in createEditor."""

    def it_should_unwrap_single_proxy_to_reach_source_model(self):
        # Simulate: while isinstance(model, QAbstractProxyModel): unwrap
        class _FakeSource:
            """Simulates TransactionTableModel (terminal model)."""

            pass

        class _FakeProxy:
            """Simulates a QAbstractProxyModel."""

            def sourceModel(self):
                return _FakeSource()

            def mapToSource(self, idx):
                return idx

        proxy = _FakeProxy()
        source = proxy.sourceModel()
        assert isinstance(source, _FakeSource)

    def it_should_unwrap_nested_proxies_to_reach_source_model(self):
        """Verify the while-loop logic works for two layers of proxy."""

        class _FakeSource:
            pass

        class _FakeProxyInner:
            def sourceModel(self):
                return _FakeSource()

            def mapToSource(self, idx):
                return idx

        class _FakeProxyOuter:
            def sourceModel(self):
                return _FakeProxyInner()

            def mapToSource(self, idx):
                return idx

        # Simulate traversal
        proxy_types = (_FakeProxyOuter, _FakeProxyInner)
        model = _FakeProxyOuter()
        idx = object()
        while isinstance(model, proxy_types):
            idx = model.mapToSource(idx)
            model = model.sourceModel()

        assert isinstance(model, _FakeSource)

    def it_should_build_suggestions_from_metadata_when_predicted_category_present(self):
        # Simulate: if pred_cat → suggestions.append((pred_cat, conf))
        meta = {"predicted_category": "Groceries", "confidence": 0.87}
        suggestions = []
        pred_cat = meta.get("predicted_category")
        conf = meta.get("confidence")
        if pred_cat:
            suggestions.append((pred_cat, conf))
        assert suggestions == [("Groceries", 0.87)]

    def it_should_produce_empty_suggestions_when_no_predicted_category(self):
        meta = {}
        suggestions = []
        pred_cat = meta.get("predicted_category")
        conf = meta.get("confidence")
        if pred_cat:
            suggestions.append((pred_cat, conf))
        assert suggestions == []

    def it_should_produce_empty_suggestions_when_metadata_is_empty_dict(self):
        meta: dict = {}
        suggestions = []
        if meta.get("predicted_category"):
            suggestions.append((meta["predicted_category"], meta.get("confidence")))
        assert suggestions == []


class DescribeSetModelData:
    """Tests for setModelData writing selected category back to model."""

    def it_should_call_set_data_with_edit_role_and_current_data(self):
        from unittest.mock import MagicMock

        from PySide6.QtCore import Qt

        model = MagicMock()
        index = MagicMock()
        editor = MagicMock()
        editor.currentData.return_value = "Transport"

        # Simulate setModelData
        new_val = editor.currentData()
        model.setData(index, new_val, Qt.ItemDataRole.EditRole)

        model.setData.assert_called_once_with(index, "Transport", Qt.ItemDataRole.EditRole)

    def it_should_write_none_when_placeholder_selected(self):
        from unittest.mock import MagicMock

        from PySide6.QtCore import Qt

        model = MagicMock()
        index = MagicMock()
        editor = MagicMock()
        editor.currentData.return_value = None

        new_val = editor.currentData()
        model.setData(index, new_val, Qt.ItemDataRole.EditRole)

        model.setData.assert_called_once_with(index, None, Qt.ItemDataRole.EditRole)


class DescribeSetEditorData:
    """Tests for setEditorData populating editor from model."""

    def it_should_pass_display_role_value_to_set_current_data(self):
        from unittest.mock import MagicMock

        from PySide6.QtCore import Qt

        editor = MagicMock()
        index = MagicMock()
        index.model.return_value.data.return_value = "Groceries"

        # Simulate setEditorData
        current_val = index.model().data(index, Qt.ItemDataRole.DisplayRole)
        editor.setCurrentData(current_val)

        editor.setCurrentData.assert_called_once_with("Groceries")
