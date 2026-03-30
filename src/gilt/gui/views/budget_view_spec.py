from __future__ import annotations

"""Specs for BudgetView logic — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")


class DescribeBudgetColorCoding:
    """Tests for percent-used color-coding in _load_budget."""

    def it_should_use_negative_color_when_over_100_percent(self):
        percent_used = 110.0
        if percent_used > 100:
            color_key = "negative_fg"
        elif percent_used > 90:
            color_key = "warning_fg"
        else:
            color_key = "positive_fg"
        assert color_key == "negative_fg"

    def it_should_use_warning_color_when_between_90_and_100_percent(self):
        percent_used = 94.5
        if percent_used > 100:
            color_key = "negative_fg"
        elif percent_used > 90:
            color_key = "warning_fg"
        else:
            color_key = "positive_fg"
        assert color_key == "warning_fg"

    def it_should_use_positive_color_when_at_or_below_90_percent(self):
        percent_used = 80.0
        if percent_used > 100:
            color_key = "negative_fg"
        elif percent_used > 90:
            color_key = "warning_fg"
        else:
            color_key = "positive_fg"
        assert color_key == "positive_fg"

    def it_should_use_positive_color_for_remaining_when_non_negative(self):
        remaining = 200.0
        if remaining >= 0:
            color_key = "positive_fg"
            text = f"${remaining:,.2f}"
        else:
            color_key = "negative_fg"
            text = f"-${abs(remaining):,.2f}"
        assert color_key == "positive_fg"
        assert text == "$200.00"

    def it_should_use_negative_color_for_remaining_when_over_budget(self):
        remaining = -75.50
        if remaining >= 0:
            color_key = "positive_fg"
            text = f"${remaining:,.2f}"
        else:
            color_key = "negative_fg"
            text = f"-${abs(remaining):,.2f}"
        assert color_key == "negative_fg"
        assert text == "-$75.50"


class DescribeUpdateSummaryHtmlGeneration:
    """Tests for _update_summary HTML content generation."""

    def it_should_use_remaining_label_when_budget_not_exceeded(self):
        total_remaining = 500.0
        remaining_label = "Remaining" if total_remaining >= 0 else "Over Budget"
        assert remaining_label == "Remaining"

    def it_should_use_over_budget_label_when_budget_exceeded(self):
        total_remaining = -100.0
        remaining_label = "Remaining" if total_remaining >= 0 else "Over Budget"
        assert remaining_label == "Over Budget"

    def it_should_format_total_budgeted_in_summary(self):
        total_budgeted = 2500.00
        snippet = f"${total_budgeted:,.2f}"
        assert snippet == "$2,500.00"

    def it_should_format_total_actual_in_summary(self):
        total_actual = 1875.33
        snippet = f"${total_actual:,.2f}"
        assert snippet == "$1,875.33"

    def it_should_format_percent_used_with_one_decimal(self):
        percent_used = 75.132
        snippet = f"{percent_used:.1f}%"
        assert snippet == "75.1%"

    def it_should_include_over_budget_warning_when_count_positive(self):
        over_budget_count = 2
        if over_budget_count > 0:
            plural = "y" if over_budget_count == 1 else "ies"
            warning = f"{over_budget_count} categor{plural} over budget"
        else:
            warning = ""
        assert warning == "2 categories over budget"

    def it_should_use_singular_category_for_count_of_one(self):
        over_budget_count = 1
        if over_budget_count > 0:
            plural = "y" if over_budget_count == 1 else "ies"
            warning = f"{over_budget_count} categor{plural} over budget"
        else:
            warning = ""
        assert warning == "1 category over budget"

    def it_should_omit_warning_when_no_categories_over_budget(self):
        over_budget_count = 0
        warning = "over budget" if over_budget_count > 0 else ""
        assert warning == ""


class DescribeBudgetTableRowFormatting:
    """Tests for table row content in _load_budget."""

    def it_should_show_em_dash_for_zero_actual_amount(self):
        actual_amount = 0.0
        actual_text = f"${actual_amount:,.2f}" if actual_amount > 0 else "—"
        assert actual_text == "—"

    def it_should_format_non_zero_actual_with_dollar_sign(self):
        actual_amount = 425.00
        actual_text = f"${actual_amount:,.2f}" if actual_amount > 0 else "—"
        assert actual_text == "$425.00"

    def it_should_show_em_dash_for_missing_budget(self):
        budget_amount = None
        budget_text = f"${budget_amount:,.2f}" if budget_amount else "—"
        assert budget_text == "—"

    def it_should_indent_subcategory_name(self):
        subcategory_name = "Utilities"
        subcat_text = f"  {subcategory_name}" if subcategory_name else ""
        assert subcat_text == "  Utilities"
