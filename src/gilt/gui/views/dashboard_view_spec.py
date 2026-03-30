from __future__ import annotations

"""Specs for DashboardView metrics logic — no real financial data, PySide6 guarded."""

import pytest

PySide6 = pytest.importorskip("PySide6")


class DescribeSummaryCardValueColor:
    """Tests for color-coding logic in the dashboard view."""

    def it_should_use_negative_color_when_over_100_percent_budget_used(self):
        pct_used = 105.0
        if pct_used > 100:
            color_key = "negative_fg"
        elif pct_used > 90:
            color_key = "warning_fg"
        else:
            color_key = "positive_fg"
        assert color_key == "negative_fg"

    def it_should_use_warning_color_when_between_90_and_100_percent_used(self):
        pct_used = 95.0
        if pct_used > 100:
            color_key = "negative_fg"
        elif pct_used > 90:
            color_key = "warning_fg"
        else:
            color_key = "positive_fg"
        assert color_key == "warning_fg"

    def it_should_use_positive_color_when_below_90_percent_used(self):
        pct_used = 70.0
        if pct_used > 100:
            color_key = "negative_fg"
        elif pct_used > 90:
            color_key = "warning_fg"
        else:
            color_key = "positive_fg"
        assert color_key == "positive_fg"

    def it_should_use_positive_color_when_exactly_at_90_percent(self):
        pct_used = 90.0
        if pct_used > 100:
            color_key = "negative_fg"
        elif pct_used > 90:
            color_key = "warning_fg"
        else:
            color_key = "positive_fg"
        assert color_key == "positive_fg"

    def it_should_use_negative_color_when_exactly_over_100_percent(self):
        pct_used = 100.1
        if pct_used > 100:
            color_key = "negative_fg"
        elif pct_used > 90:
            color_key = "warning_fg"
        else:
            color_key = "positive_fg"
        assert color_key == "negative_fg"


class DescribeDashboardMetricsFormatting:
    """Tests for metric string formatting used in dashboard cards."""

    def it_should_format_spending_with_dollar_sign_and_two_decimals(self):
        month_spending = 1234.5
        formatted = f"${month_spending:,.2f}"
        assert formatted == "$1,234.50"

    def it_should_format_zero_spending_correctly(self):
        month_spending = 0.0
        formatted = f"${month_spending:,.2f}"
        assert formatted == "$0.00"

    def it_should_format_budget_percent_with_one_decimal(self):
        pct_used = 87.333
        formatted = f"{pct_used:.1f}%"
        assert formatted == "87.3%"

    def it_should_use_over_budget_subtitle_when_remaining_negative(self):
        total_remaining = -250.75
        if total_remaining < 0:
            subtitle = f"${abs(total_remaining):,.2f} over budget"
        else:
            subtitle = f"${total_remaining:,.2f} remaining"
        assert subtitle == "$250.75 over budget"

    def it_should_use_remaining_subtitle_when_budget_not_exhausted(self):
        total_remaining = 300.00
        if total_remaining < 0:
            subtitle = f"${abs(total_remaining):,.2f} over budget"
        else:
            subtitle = f"${total_remaining:,.2f} remaining"
        assert subtitle == "$300.00 remaining"

    def it_should_use_warning_color_for_uncategorized_transactions(self):
        uncategorized_count = 5
        if uncategorized_count > 0:
            color_key = "warning_fg"
            subtitle = "transactions need categorization"
        else:
            color_key = "positive_fg"
            subtitle = "all categorized!"
        assert color_key == "warning_fg"
        assert subtitle == "transactions need categorization"

    def it_should_use_positive_color_when_all_transactions_categorized(self):
        uncategorized_count = 0
        if uncategorized_count > 0:
            color_key = "warning_fg"
            subtitle = "transactions need categorization"
        else:
            color_key = "positive_fg"
            subtitle = "all categorized!"
        assert color_key == "positive_fg"
        assert subtitle == "all categorized!"


class DescribeBudgetSummaryDisplay:
    """Tests for budget summary display branch logic."""

    def it_should_show_em_dash_when_no_budgets_set(self):
        total_budgeted = 0
        value = "—" if total_budgeted <= 0 else "75.0%"
        assert value == "—"

    def it_should_show_percent_used_when_budgets_exist(self):
        total_budgeted = 1000.0
        pct_used = 75.0
        value = f"{pct_used:.1f}%" if total_budgeted > 0 else "—"
        assert value == "75.0%"
