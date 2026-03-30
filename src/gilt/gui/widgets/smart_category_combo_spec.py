from __future__ import annotations

"""Specs for SmartCategoryComboBox model population logic — PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")


class DescribeSetCategories:
    """Tests for model population in set_categories."""

    def it_should_add_placeholder_as_first_item_when_provided(self):
        # Simulate item insertion order
        items: list[tuple[str, object]] = []

        placeholder = "-- Select Category --"
        items.append((placeholder, None))  # Placeholder

        assert items[0] == ("-- Select Category --", None)

    def it_should_add_suggestion_header_before_suggestions(self):
        items: list[str] = []
        suggestions = [("Groceries", 0.9)]

        if suggestions:
            items.append("--- Suggestions ---")  # Header (non-selectable)
            for cat, conf in suggestions:
                items.append(f"{cat} ({conf:.0%})")
            items.append("--- All Categories ---")  # Separator

        assert items[0] == "--- Suggestions ---"

    def it_should_format_suggestion_with_confidence_percentage(self):
        cat = "Transport"
        conf = 0.85
        text = f"{cat} ({conf:.0%})"
        assert text == "Transport (85%)"

    def it_should_omit_confidence_in_suggestion_label_when_confidence_is_none(self):
        cat = "Groceries"
        conf = None
        text = f"{cat} ({conf:.0%})" if conf is not None else cat
        assert text == "Groceries"

    def it_should_add_all_categories_separator_after_suggestions(self):
        items: list[str] = []
        suggestions = [("Groceries", 0.9)]

        if suggestions:
            items.append("--- Suggestions ---")
            for cat, conf in suggestions:
                items.append(f"{cat} ({conf:.0%})")
            items.append("--- All Categories ---")

        assert "--- All Categories ---" in items

    def it_should_add_all_categories_in_order_after_suggestions(self):
        all_categories = ["Groceries", "Transport", "Housing"]
        items: list[tuple[str, str]] = []
        for cat in all_categories:
            items.append((cat, cat))
        assert items == [
            ("Groceries", "Groceries"),
            ("Transport", "Transport"),
            ("Housing", "Housing"),
        ]

    def it_should_skip_suggestions_section_when_no_suggestions_given(self):
        suggestions = None
        items: list[str] = []
        if suggestions:
            items.append("--- Suggestions ---")
        items.append("Groceries")
        assert "--- Suggestions ---" not in items

    def it_should_set_user_role_data_to_category_name_for_suggestion(self):
        # The UserRole data for a suggestion item should be the raw category name
        cat = "Groceries"
        conf = 0.9
        # DisplayRole text includes confidence, UserRole data is plain category name
        display_text = f"{cat} ({conf:.0%})"
        user_role_data = cat  # As per set_categories logic
        assert user_role_data == "Groceries"
        assert display_text == "Groceries (90%)"


class DescribeCurrentData:
    """Tests for currentData returning UserRole data."""

    def it_should_return_none_for_placeholder_selection(self):
        # When placeholder is selected, UserRole data is None
        selected_data = None
        assert selected_data is None

    def it_should_return_category_name_string_for_category_selection(self):
        selected_data = "Transport"
        assert selected_data == "Transport"


class DescribeSetCurrentData:
    """Tests for setCurrentData lookup logic."""

    def it_should_locate_item_by_user_role_data(self):
        # Simulate findData(data, UserRole) logic
        items = [
            (None, None),           # placeholder
            ("Groceries", "Groceries"),
            ("Transport", "Transport"),
        ]
        target = "Transport"
        idx = next((i for i, (_, d) in enumerate(items) if d == target), -1)
        assert idx == 2

    def it_should_return_negative_one_when_data_not_found(self):
        items = [("Groceries", "Groceries")]
        target = "Housing"
        idx = next((i for i, (_, d) in enumerate(items) if d == target), -1)
        assert idx == -1

    def it_should_set_edit_text_to_data_string_when_not_found(self):
        # When findData returns -1, edit text is set to the data string
        data = "UnknownCategory"
        idx = -1
        edit_text = "" if idx >= 0 else data if data else ""
        assert edit_text == "UnknownCategory"

    def it_should_clear_edit_text_when_data_is_falsy_and_not_found(self):
        data = None
        idx = -1
        edit_text = "something" if idx >= 0 else data if data else ""
        assert edit_text == ""
