from __future__ import annotations

"""Specs for gilt.util.dates — pure ISO-date parsing and formatting helpers."""

from datetime import date

import pytest


class DescribeParsIsoDate:
    def it_should_parse_a_valid_iso_date_string(self):
        from gilt.util.dates import parse_iso_date

        result = parse_iso_date("2025-03-01")

        assert result == date(2025, 3, 1)

    def it_should_raise_value_error_for_an_invalid_date_string(self):
        from gilt.util.dates import parse_iso_date

        with pytest.raises(ValueError) as exc_info:
            parse_iso_date("not-a-date")

        message = str(exc_info.value)
        assert "not-a-date" in message
        assert "Expected YYYY-MM-DD" in message

    def it_should_include_the_offending_value_in_the_error_message(self):
        from gilt.util.dates import parse_iso_date

        with pytest.raises(ValueError) as exc_info:
            parse_iso_date("2025-13-01")

        assert "2025-13-01" in str(exc_info.value)


class DescribeFormatIsoDate:
    def it_should_format_a_date_as_yyyy_mm_dd(self):
        from gilt.util.dates import format_iso_date

        result = format_iso_date(date(2025, 3, 1))

        assert result == "2025-03-01"

    def it_should_zero_pad_month_and_day(self):
        from gilt.util.dates import format_iso_date

        result = format_iso_date(date(2025, 1, 5))

        assert result == "2025-01-05"
