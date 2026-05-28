from __future__ import annotations

"""Tests for fiscal_year_range helper."""

from datetime import date

import pytest

from gilt.util.fy import fiscal_year_range


class DescribeFiscalYearRange:
    """Tests for the fiscal_year_range helper."""

    def it_should_parse_two_digit_fy_uppercase(self):
        start, end = fiscal_year_range("FY25")
        assert start == date(2024, 11, 1)
        assert end == date(2025, 10, 31)

    def it_should_parse_two_digit_fy_lowercase(self):
        start, end = fiscal_year_range("fy25")
        assert start == date(2024, 11, 1)
        assert end == date(2025, 10, 31)

    def it_should_parse_four_digit_fy_uppercase(self):
        start, end = fiscal_year_range("FY2025")
        assert start == date(2024, 11, 1)
        assert end == date(2025, 10, 31)

    def it_should_parse_four_digit_fy_lowercase(self):
        start, end = fiscal_year_range("fy2025")
        assert start == date(2024, 11, 1)
        assert end == date(2025, 10, 31)

    def it_should_treat_two_and_four_digit_forms_as_identical(self):
        short = fiscal_year_range("FY25")
        long = fiscal_year_range("FY2025")
        assert short == long

    def it_should_include_november_1_start_boundary(self):
        start, _ = fiscal_year_range("FY25")
        assert start == date(2024, 11, 1)

    def it_should_include_october_31_end_boundary(self):
        _, end = fiscal_year_range("FY25")
        assert end == date(2025, 10, 31)

    def it_should_handle_fy_with_leading_whitespace(self):
        start, end = fiscal_year_range("  FY25")
        assert start == date(2024, 11, 1)
        assert end == date(2025, 10, 31)

    def it_should_parse_mixed_case(self):
        start, end = fiscal_year_range("Fy25")
        assert start == date(2024, 11, 1)
        assert end == date(2025, 10, 31)

    def it_should_reject_bare_year_number(self):
        with pytest.raises(ValueError, match="Invalid fiscal year format"):
            fiscal_year_range("25")

    def it_should_reject_year_without_fy_prefix(self):
        with pytest.raises(ValueError, match="Invalid fiscal year format"):
            fiscal_year_range("2025")

    def it_should_reject_fy_prefix_alone(self):
        with pytest.raises(ValueError, match="Invalid fiscal year format"):
            fiscal_year_range("FY")

    def it_should_reject_fy_with_single_digit(self):
        with pytest.raises(ValueError, match="Invalid fiscal year format"):
            fiscal_year_range("FY5")

    def it_should_reject_fy_with_three_digits(self):
        with pytest.raises(ValueError, match="Invalid fiscal year format"):
            fiscal_year_range("FY025")

    def it_should_reject_fy_with_non_numeric_suffix(self):
        with pytest.raises(ValueError, match="Invalid fiscal year format"):
            fiscal_year_range("FYAB")

    def it_should_compute_correct_prior_year_boundary(self):
        # FY26 should start Nov 1 2025 and end Oct 31 2026
        start, end = fiscal_year_range("FY26")
        assert start == date(2025, 11, 1)
        assert end == date(2026, 10, 31)

    def it_should_parse_fy99_as_2099(self):
        # Two-digit years always map to 20xx
        start, end = fiscal_year_range("FY99")
        assert start == date(2098, 11, 1)
        assert end == date(2099, 10, 31)
