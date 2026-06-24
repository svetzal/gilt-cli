from __future__ import annotations

from datetime import date

from gilt.cli.formatting import (
    base_match_row,
    build_category_path,
    category_preview_row,
    fmt_colored_amount,
    format_prefix_lookup_error,
)
from gilt.model.account import Transaction
from gilt.services.transaction_operations_service import TransactionLookupResult


class DescribeFmtColoredAmount:
    def it_should_return_red_markup_for_negative_amounts(self):
        result = fmt_colored_amount(-42.50)

        assert result == "[red]$-42.50[/]"

    def it_should_return_green_markup_for_positive_amounts(self):
        result = fmt_colored_amount(100.00)

        assert result == "[green]$100.00[/]"

    def it_should_return_plain_string_for_zero(self):
        result = fmt_colored_amount(0.0)

        assert result == "$0.00"

    def it_should_add_bold_to_red_markup_when_bold_is_true(self):
        result = fmt_colored_amount(-42.50, bold=True)

        assert result == "[red bold]$-42.50[/]"

    def it_should_add_bold_to_green_markup_when_bold_is_true(self):
        result = fmt_colored_amount(100.00, bold=True)

        assert result == "[green bold]$100.00[/]"

    def it_should_wrap_zero_in_bold_markup_when_bold_is_true(self):
        result = fmt_colored_amount(0.0, bold=True)

        assert result == "[bold]$0.00[/]"

    def it_should_respect_custom_prefix(self):
        result = fmt_colored_amount(-10.0, prefix="")

        assert result == "[red]-10.00[/]"


class DescribeFormatPrefixLookupError:
    def it_should_return_prefix_too_short_message(self):
        result = TransactionLookupResult(transaction=None, error="prefix_too_short")

        msg = format_prefix_lookup_error(result, "abc")

        assert "8 characters" in msg
        assert "'abc'" in msg

    def it_should_return_not_found_message(self):
        result = TransactionLookupResult(transaction=None, error="not_found")

        msg = format_prefix_lookup_error(result, "abcd1234")

        assert "No transaction" in msg
        assert "'abcd1234'" in msg

    def it_should_return_ambiguous_message_with_sample_ids(self):
        result = TransactionLookupResult(
            transaction=None,
            error="ambiguous",
            ambiguous_matches=["abcd1234abcd0001", "abcd1234abcd0002"],
        )

        msg = format_prefix_lookup_error(result, "abcd1234")

        assert "Ambiguous" in msg
        assert "abcd1234abcd0001" in msg
        assert "abcd1234abcd0002" in msg

    def it_should_handle_empty_ambiguous_matches(self):
        result = TransactionLookupResult(transaction=None, error="ambiguous", ambiguous_matches=[])

        msg = format_prefix_lookup_error(result, "abcd1234")

        assert "Ambiguous" in msg
        assert "'abcd1234'" in msg


class DescribeBaseMatchRow:
    def it_should_return_five_element_tuple(self):
        t = Transaction(
            transaction_id="abcd1234abcd1234",
            date=date(2025, 1, 15),
            description="EXAMPLE UTILITY PAYMENT",
            amount=-42.50,
            currency="CAD",
            account_id="MYBANK_CHQ",
        )

        result = base_match_row("MYBANK_CHQ", t)

        assert result == (
            "MYBANK_CHQ",
            "abcd1234",
            "2025-01-15",
            "EXAMPLE UTILITY PAYMENT",
            "$-42.50",
        )

    def it_should_truncate_transaction_id_to_eight_chars(self):
        t = Transaction(
            transaction_id="abcd1234efgh5678",
            date=date(2025, 1, 1),
            description="Test",
            amount=-10.0,
            currency="CAD",
            account_id="ACC",
        )

        result = base_match_row("ACC", t)

        assert result[1] == "abcd1234"

    def it_should_truncate_description_to_forty_chars(self):
        t = Transaction(
            transaction_id="abcd1234abcd1234",
            date=date(2025, 1, 1),
            description="A" * 50,
            amount=-10.0,
            currency="CAD",
            account_id="ACC",
        )

        result = base_match_row("ACC", t)

        assert result[3] == "A" * 40

    def it_should_handle_empty_description(self):
        t = Transaction(
            transaction_id="abcd1234abcd1234",
            date=date(2025, 1, 1),
            description="",
            amount=-10.0,
            currency="CAD",
            account_id="ACC",
        )

        result = base_match_row("ACC", t)

        assert result[3] == ""


class DescribeCategoryPreviewRow:
    def it_should_return_six_element_tuple_with_category_appended(self):
        t = Transaction(
            transaction_id="abcd1234abcd1234",
            date=date(2025, 1, 15),
            description="EXAMPLE UTILITY PAYMENT",
            amount=-42.50,
            currency="CAD",
            account_id="MYBANK_CHQ",
        )

        result = category_preview_row("MYBANK_CHQ", t, "Utilities:Electricity")

        assert len(result) == 6
        assert result[5] == "Utilities:Electricity"

    def it_should_include_base_row_fields_as_first_five_elements(self):
        t = Transaction(
            transaction_id="abcd1234abcd1234",
            date=date(2025, 2, 1),
            description="ACME CORP",
            amount=-99.00,
            currency="CAD",
            account_id="MYBANK_CC",
        )

        result = category_preview_row("MYBANK_CC", t, "Shopping")

        assert result[:5] == base_match_row("MYBANK_CC", t)

    def it_should_accept_empty_category_path(self):
        t = Transaction(
            transaction_id="abcd1234abcd1234",
            date=date(2025, 3, 1),
            description="SAMPLE STORE",
            amount=-10.00,
            currency="CAD",
            account_id="MYBANK_CHQ",
        )

        result = category_preview_row("MYBANK_CHQ", t, "")

        assert result[5] == ""


class DescribeBuildCategoryPath:
    def it_should_split_colon_syntax_into_category_and_subcategory(self):
        cat, subcat, warning = build_category_path("Food:Groceries")

        assert cat == "Food"
        assert subcat == "Groceries"
        assert warning is None

    def it_should_return_empty_cat_for_empty_input(self):
        cat, subcat, warning = build_category_path("")

        assert cat == ""
        assert subcat is None
        assert warning is None

    def it_should_return_warning_when_subcategory_conflicts_with_colon_syntax(self):
        cat, subcat, warning = build_category_path("Food:Groceries", subcategory="Dining")

        assert cat == "Food"
        assert subcat == "Groceries"
        assert warning is not None
        assert "--subcategory" in warning or "subcategory" in warning.lower()

    def it_should_prefer_colon_subcat_over_separate_subcategory_arg(self):
        cat, subcat, warning = build_category_path("Food:Groceries", subcategory="Dining")

        assert subcat == "Groceries"

    def it_should_accept_subcategory_when_no_colon_in_category(self):
        cat, subcat, warning = build_category_path("Food", subcategory="Groceries")

        assert cat == "Food"
        assert subcat == "Groceries"
        assert warning is None

    def it_should_return_category_only_when_no_colon_and_no_subcategory(self):
        cat, subcat, warning = build_category_path("Food")

        assert cat == "Food"
        assert subcat is None
        assert warning is None
