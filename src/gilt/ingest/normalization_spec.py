"""Specs for gilt.ingest.normalization — pure transaction ID and normalization logic."""

from __future__ import annotations

import hashlib
from pathlib import Path

import pandas as pd
import pytest

from gilt.ingest.normalization import (
    HASH_ALGO_SPEC,
    _build_transaction_dataframe,
    _build_amount_series,
    _build_date_series,
    _build_description_series,
    build_transaction_id,
)


class DescribeBuildTransactionId:
    def it_should_produce_a_16_hex_char_string(self):
        result = build_transaction_id("MYBANK_CHQ", "2024-01-15", -42.50, "EXAMPLE UTILITY")
        assert len(result) == 16
        assert all(c in "0123456789abcdef" for c in result)

    def it_should_match_frozen_sha256_spec(self):
        account_id = "MYBANK_CHQ"
        date = "2024-01-15"
        amount = -42.5
        description = "EXAMPLE UTILITY"
        base = f"{account_id}|{date}|{amount}|{description}"
        expected = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]

        assert build_transaction_id(account_id, date, amount, description) == expected

    def it_should_differ_when_description_changes(self):
        id1 = build_transaction_id("MYBANK_CHQ", "2024-01-15", -42.50, "EXAMPLE UTILITY")
        id2 = build_transaction_id("MYBANK_CHQ", "2024-01-15", -42.50, "SAMPLE STORE")
        assert id1 != id2

    def it_should_differ_when_amount_changes(self):
        id1 = build_transaction_id("MYBANK_CHQ", "2024-01-15", -42.50, "EXAMPLE UTILITY")
        id2 = build_transaction_id("MYBANK_CHQ", "2024-01-15", -99.99, "EXAMPLE UTILITY")
        assert id1 != id2

    def it_should_differ_when_account_changes(self):
        id1 = build_transaction_id("MYBANK_CHQ", "2024-01-15", -42.50, "EXAMPLE UTILITY")
        id2 = build_transaction_id("BANK2_BIZ", "2024-01-15", -42.50, "EXAMPLE UTILITY")
        assert id1 != id2

    def it_should_preserve_hash_algo_spec_string(self):
        assert "v1: sha256" in HASH_ALGO_SPEC
        assert "account_id|date|amount|description" in HASH_ALGO_SPEC


class DescribeResolveAmountSeries:
    def _make_df(self, values, col="Amount"):
        return pd.DataFrame({col: values})

    def it_should_parse_plain_numeric_values(self):
        df = self._make_df(["-42.50", "100.00"])
        column_map = {"amount": "Amount", "usd": None}
        result = _build_amount_series(df, column_map, {}, "expenses_negative")
        assert list(result) == pytest.approx([-42.50, 100.00])

    def it_should_strip_dollar_signs_and_commas(self):
        df = self._make_df(["$1,234.56", "-$99.99"])
        column_map = {"amount": "Amount", "usd": None}
        result = _build_amount_series(df, column_map, {}, "expenses_negative")
        assert result.iloc[0] == pytest.approx(1234.56)
        assert result.iloc[1] == pytest.approx(-99.99)

    def it_should_convert_parenthesized_values_to_negative(self):
        df = self._make_df(["(123.45)"])
        column_map = {"amount": "Amount", "usd": None}
        result = _build_amount_series(df, column_map, {}, "expenses_negative")
        assert result.iloc[0] == pytest.approx(-123.45)

    def it_should_negate_amounts_when_expenses_positive(self):
        df = self._make_df(["50.00", "-20.00"])
        column_map = {"amount": "Amount", "usd": None}
        result = _build_amount_series(df, column_map, {}, "expenses_positive")
        assert result.iloc[0] == pytest.approx(-50.00)
        assert result.iloc[1] == pytest.approx(20.00)

    def it_should_fall_back_to_usd_column_when_amount_absent(self):
        df = pd.DataFrame({"USD$": ["75.00"]})
        column_map = {"amount": None, "usd": "USD$"}
        result = _build_amount_series(df, column_map, {}, "expenses_negative")
        assert result.iloc[0] == pytest.approx(75.00)

    def it_should_produce_nan_for_non_numeric_values(self):
        df = self._make_df(["not-a-number"])
        column_map = {"amount": "Amount", "usd": None}
        result = _build_amount_series(df, column_map, {}, "expenses_negative")
        assert pd.isna(result.iloc[0])

    def it_should_use_override_series_when_provided(self):
        df = self._make_df(["ignored"])
        column_map = {"amount": "Amount", "usd": None}
        override = pd.Series(["99.99"])
        result = _build_amount_series(df, column_map, {"amount_series": override}, "expenses_negative")
        assert result.iloc[0] == pytest.approx(99.99)


class DescribeResolveDateSeries:
    def it_should_format_valid_dates_as_yyyy_mm_dd(self):
        df = pd.DataFrame({"Date": ["2024-01-15", "2024-12-31"]})
        column_map = {"date": "Date"}
        result = _build_date_series(df, column_map, {})
        assert list(result) == ["2024-01-15", "2024-12-31"]

    def it_should_return_nat_string_for_invalid_dates(self):
        df = pd.DataFrame({"Date": ["not-a-date"]})
        column_map = {"date": "Date"}
        result = _build_date_series(df, column_map, {})
        assert pd.isna(result.iloc[0]) or result.iloc[0] == "NaT"

    def it_should_use_override_series_over_column_map(self):
        df = pd.DataFrame({"Date": ["2020-01-01"]})
        column_map = {"date": "Date"}
        override = pd.Series(["2024-06-15"])
        result = _build_date_series(df, column_map, {"date_series": override})
        assert result.iloc[0] == "2024-06-15"


class DescribeResolveDescriptionSeries:
    def it_should_return_desc1_when_desc2_is_empty(self):
        df = pd.DataFrame({"Description 1": ["EXAMPLE UTILITY"], "Description 2": [""]})
        column_map = {"desc1": "Description 1", "desc2": "Description 2"}
        result = _build_description_series(df, column_map, {})
        assert result.iloc[0] == "EXAMPLE UTILITY"

    def it_should_join_desc1_and_desc2_with_dash(self):
        df = pd.DataFrame({"Description 1": ["SAMPLE STORE"], "Description 2": ["REF1234"]})
        column_map = {"desc1": "Description 1", "desc2": "Description 2"}
        result = _build_description_series(df, column_map, {})
        assert result.iloc[0] == "SAMPLE STORE - REF1234"

    def it_should_not_append_empty_desc2(self):
        df = pd.DataFrame({"Description 1": ["ACME CORP"], "Description 2": [None]})
        column_map = {"desc1": "Description 1", "desc2": "Description 2"}
        result = _build_description_series(df, column_map, {})
        assert result.iloc[0] == "ACME CORP"

    def it_should_handle_missing_desc2_column(self):
        df = pd.DataFrame({"Description 1": ["EXAMPLE UTILITY"]})
        column_map = {"desc1": "Description 1", "desc2": None}
        result = _build_description_series(df, column_map, {})
        assert result.iloc[0] == "EXAMPLE UTILITY"


class DescribeBuildTransactionDataframe:
    def it_should_produce_all_standard_schema_columns(self):
        df = pd.DataFrame({
            "Date": ["2024-01-15"],
            "Description": ["EXAMPLE UTILITY"],
            "Amount": ["-42.50"],
        })
        column_map = {"date": "Date", "desc1": "Description", "desc2": None,
                      "amount": "Amount", "usd": None, "currency": None}
        result = _build_transaction_dataframe(
            df, column_map, {}, "MYBANK_CHQ", "expenses_negative", Path("mybank_jan.csv")
        )
        for col in ["date", "description", "amount", "currency", "account_id",
                    "counterparty", "category", "subcategory", "notes",
                    "source_file", "transaction_id"]:
            assert col in result.columns

    def it_should_set_counterparty_equal_to_description(self):
        df = pd.DataFrame({
            "Date": ["2024-01-15"],
            "Description": ["ACME CORP"],
            "Amount": ["-10.00"],
        })
        column_map = {"date": "Date", "desc1": "Description", "desc2": None,
                      "amount": "Amount", "usd": None, "currency": None}
        result = _build_transaction_dataframe(
            df, column_map, {}, "MYBANK_CHQ", "expenses_negative", Path("mybank.csv")
        )
        assert result.iloc[0]["counterparty"] == result.iloc[0]["description"]

    def it_should_set_account_id_from_parameter(self):
        df = pd.DataFrame({
            "Date": ["2024-03-01"],
            "Description": ["SAMPLE STORE"],
            "Amount": ["-5.00"],
        })
        column_map = {"date": "Date", "desc1": "Description", "desc2": None,
                      "amount": "Amount", "usd": None, "currency": None}
        result = _build_transaction_dataframe(
            df, column_map, {}, "BANK2_BIZ", "expenses_negative", Path("bank2.csv")
        )
        assert result.iloc[0]["account_id"] == "BANK2_BIZ"

    def it_should_default_currency_to_cad_when_absent(self):
        df = pd.DataFrame({
            "Date": ["2024-03-01"],
            "Description": ["EXAMPLE UTILITY"],
            "Amount": ["-5.00"],
        })
        column_map = {"date": "Date", "desc1": "Description", "desc2": None,
                      "amount": "Amount", "usd": None, "currency": None}
        result = _build_transaction_dataframe(
            df, column_map, {}, "MYBANK_CHQ", "expenses_negative", Path("mybank.csv")
        )
        assert result.iloc[0]["currency"] == "CAD"

    def it_should_compute_deterministic_transaction_id(self):
        df = pd.DataFrame({
            "Date": ["2024-01-15"],
            "Description": ["EXAMPLE UTILITY"],
            "Amount": ["-42.5"],
        })
        column_map = {"date": "Date", "desc1": "Description", "desc2": None,
                      "amount": "Amount", "usd": None, "currency": None}
        result = _build_transaction_dataframe(
            df, column_map, {}, "MYBANK_CHQ", "expenses_negative", Path("mybank.csv")
        )
        row = result.iloc[0]
        expected = build_transaction_id(
            row["account_id"], row["date"], row["amount"], row["description"]
        )
        assert row["transaction_id"] == expected
