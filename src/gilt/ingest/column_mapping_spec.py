"""Specs for gilt.ingest.column_mapping — pure column detection logic."""

from __future__ import annotations

import pandas as pd

from gilt.ingest.column_mapping import (
    _RBC_REQUIRED_COLS,
    _detect_columns,
    _detect_rbc_overrides,
    _first_match,
    find_missing_columns,
)


class DescribeFirstMatch:
    def it_should_return_matching_column_case_insensitively(self):
        result = _first_match(["Date"], ["date", "Amount"])
        assert result == "date"

    def it_should_return_first_matching_candidate(self):
        # candidates are checked in order; "Transaction Date" is listed before "Date"
        result = _first_match(["Transaction Date", "Date"], ["Amount", "Date", "Transaction Date"])
        assert result == "Transaction Date"

    def it_should_return_none_when_no_match(self):
        result = _first_match(["Date"], ["Amount", "Description"])
        assert result is None

    def it_should_preserve_original_casing_of_available_column(self):
        result = _first_match(["date"], ["Date"])
        assert result == "Date"


class DescribeDetectColumns:
    def it_should_detect_date_column(self):
        result = _detect_columns(["Date", "Description", "Amount"])
        assert result["date"] == "Date"

    def it_should_detect_transaction_date_variant(self):
        result = _detect_columns(["Transaction Date", "Memo", "CAD$"])
        assert result["date"] == "Transaction Date"

    def it_should_detect_desc1_from_description(self):
        result = _detect_columns(["Date", "Description", "Amount"])
        assert result["desc1"] == "Description"

    def it_should_detect_desc1_from_payee(self):
        result = _detect_columns(["Posted Date", "Payee", "Amount"])
        assert result["desc1"] == "Payee"

    def it_should_detect_desc2(self):
        result = _detect_columns(["Date", "Description 1", "Description 2", "CAD$"])
        assert result["desc2"] == "Description 2"

    def it_should_detect_amount_from_cad(self):
        result = _detect_columns(["Date", "Description 1", "CAD$"])
        assert result["amount"] == "CAD$"

    def it_should_detect_usd_column(self):
        result = _detect_columns(["Date", "Description 1", "CAD$", "USD$"])
        assert result["usd"] == "USD$"

    def it_should_detect_currency_column(self):
        result = _detect_columns(["Date", "Description", "Amount", "Currency"])
        assert result["currency"] == "Currency"

    def it_should_return_none_for_absent_roles(self):
        result = _detect_columns(["Date", "Amount"])
        assert result["desc1"] is None
        assert result["desc2"] is None
        assert result["currency"] is None


class DescribeDetectRbcOverrides:
    def _make_rbc_df(self, shifted=True):
        data = {col: ["x"] for col in _RBC_REQUIRED_COLS}
        if shifted:
            data["Transaction Date"] = [""]
            data["Account Number"] = ["01/15/2024"]
        else:
            data["Transaction Date"] = ["01/15/2024"]
            data["Account Number"] = ["12345678"]
        return pd.DataFrame(data)

    def it_should_return_empty_dict_for_non_rbc_headers(self):
        df = pd.DataFrame({"Date": ["2024-01-15"], "Description": ["test"], "Amount": ["-10"]})
        result = _detect_rbc_overrides(df, list(df.columns))
        assert result == {}

    def it_should_return_overrides_for_rbc_shifted_format(self):
        df = self._make_rbc_df(shifted=True)
        result = _detect_rbc_overrides(df, list(df.columns))
        assert "date_series" in result
        assert "desc1_series" in result
        assert "desc2_series" in result
        assert "amount_series" in result

    def it_should_return_empty_dict_for_rbc_headers_without_shift(self):
        df = self._make_rbc_df(shifted=False)
        result = _detect_rbc_overrides(df, list(df.columns))
        assert result == {}


class DescribeFindMissingColumns:
    def it_should_return_empty_list_when_all_roles_present(self):
        column_map = {"date": "Date", "desc1": "Description", "desc2": None,
                      "amount": "Amount", "usd": None}
        result = find_missing_columns(column_map, {})
        assert result == []

    def it_should_report_missing_date(self):
        column_map = {"date": None, "desc1": "Description", "desc2": None,
                      "amount": "Amount", "usd": None}
        result = find_missing_columns(column_map, {})
        assert "date" in result

    def it_should_report_missing_description_when_both_desc_absent(self):
        column_map = {"date": "Date", "desc1": None, "desc2": None,
                      "amount": "Amount", "usd": None}
        result = find_missing_columns(column_map, {})
        assert "description" in result

    def it_should_report_missing_amount_when_both_amount_and_usd_absent(self):
        column_map = {"date": "Date", "desc1": "Description", "desc2": None,
                      "amount": None, "usd": None}
        result = find_missing_columns(column_map, {})
        assert "amount" in result

    def it_should_not_report_date_missing_when_override_present(self):
        column_map = {"date": None, "desc1": "Description", "desc2": None,
                      "amount": "Amount", "usd": None}
        result = find_missing_columns(column_map, {"date_series": "override"})
        assert "date" not in result

    def it_should_not_report_amount_missing_when_usd_present(self):
        column_map = {"date": "Date", "desc1": "Description", "desc2": None,
                      "amount": None, "usd": "USD$"}
        result = find_missing_columns(column_map, {})
        assert "amount" not in result
