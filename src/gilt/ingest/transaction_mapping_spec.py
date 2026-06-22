"""Specs for gilt.ingest.transaction_mapping — pure DataFrame ↔ model conversion."""

from __future__ import annotations

import pandas as pd
import pytest

from gilt.ingest.transaction_mapping import (
    _groups_to_dataframe,
    _opt_str,
    build_groups_from_dataframe,
    build_transactions_from_dataframe,
)
from gilt.model.account import Transaction, TransactionGroup
from gilt.model.ledger_io import STANDARD_FIELDS


def _make_transaction(**kwargs) -> Transaction:
    defaults = dict(
        transaction_id="abc1234567890000",
        date="2024-01-15",
        description="EXAMPLE UTILITY",
        amount=-42.50,
        currency="CAD",
        account_id="MYBANK_CHQ",
        counterparty="EXAMPLE UTILITY",
        category=None,
        subcategory=None,
        notes=None,
        source_file="mybank.csv",
        metadata={},
    )
    defaults.update(kwargs)
    return Transaction(**defaults)


def _make_group(**kwargs) -> TransactionGroup:
    txn = _make_transaction(**kwargs)
    return TransactionGroup(group_id=txn.transaction_id, primary=txn)


class DescribeOptStr:
    def it_should_return_none_for_none_input(self):
        assert _opt_str(None) is None

    def it_should_return_none_for_nan(self):
        assert _opt_str(float("nan")) is None

    def it_should_return_none_for_empty_string(self):
        assert _opt_str("") is None

    def it_should_return_none_for_whitespace_only(self):
        assert _opt_str("   ") is None

    def it_should_return_stripped_string_for_non_empty_value(self):
        assert _opt_str("  hello  ") == "hello"

    def it_should_return_string_representation_of_non_string(self):
        assert _opt_str(42) == "42"


class DescribeGroupsToDataframe:
    def it_should_return_empty_dataframe_with_standard_fields_for_empty_input(self):
        result = _groups_to_dataframe([])
        assert list(result.columns) == STANDARD_FIELDS
        assert len(result) == 0

    def it_should_produce_one_row_per_group(self):
        groups = [_make_group(), _make_group(transaction_id="def9876543210000")]
        result = _groups_to_dataframe(groups)
        assert len(result) == 2

    def it_should_map_primary_fields_to_columns(self):
        group = _make_group(
            transaction_id="abc1234567890000",
            description="SAMPLE STORE",
            amount=-10.00,
            account_id="MYBANK_CHQ",
        )
        result = _groups_to_dataframe([group])
        row = result.iloc[0]
        assert row["transaction_id"] == "abc1234567890000"
        assert row["description"] == "SAMPLE STORE"
        assert row["amount"] == pytest.approx(-10.00)
        assert row["account_id"] == "MYBANK_CHQ"

    def it_should_default_currency_to_cad(self):
        group = _make_group(currency=None)
        result = _groups_to_dataframe([group])
        assert result.iloc[0]["currency"] == "CAD"


class DescribeBuildGroupsFromDataframe:
    def it_should_return_one_group_per_row(self):
        df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": "2024-01-15",
            "description": "EXAMPLE UTILITY",
            "amount": -42.50,
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
            "counterparty": "EXAMPLE UTILITY",
            "category": None,
            "subcategory": None,
            "notes": None,
            "source_file": "mybank.csv",
        }])
        result = build_groups_from_dataframe(df)
        assert len(result) == 1
        assert result[0].primary.transaction_id == "abc1234567890000"

    def it_should_set_group_id_equal_to_transaction_id(self):
        df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": "2024-01-15",
            "description": "EXAMPLE UTILITY",
            "amount": -42.50,
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
            "counterparty": None,
            "category": None,
            "subcategory": None,
            "notes": None,
            "source_file": "mybank.csv",
        }])
        result = build_groups_from_dataframe(df)
        assert result[0].group_id == result[0].primary.transaction_id

    def it_should_default_nan_amount_to_zero(self):
        df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": "2024-01-15",
            "description": "EXAMPLE UTILITY",
            "amount": float("nan"),
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
            "counterparty": None,
            "category": None,
            "subcategory": None,
            "notes": None,
            "source_file": "mybank.csv",
        }])
        result = build_groups_from_dataframe(df)
        assert result[0].primary.amount == 0.0


class DescribeBuildTransactionsFromDataframe:
    def it_should_extract_transactions_from_dataframe(self):
        df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": "2024-01-15",
            "description": "ACME CORP",
            "amount": -5.00,
            "currency": "CAD",
            "account_id": "BANK2_BIZ",
            "counterparty": None,
            "category": None,
            "subcategory": None,
            "notes": None,
            "source_file": "bank2.csv",
        }])
        result = build_transactions_from_dataframe(df)
        assert len(result) == 1
        assert result[0].account_id == "BANK2_BIZ"
        assert result[0].description == "ACME CORP"


class DescribeRoundTrip:
    def it_should_preserve_primary_fields_through_groups_to_df_and_back(self):
        original_group = _make_group(
            transaction_id="abc1234567890000",
            description="EXAMPLE UTILITY",
            amount=-42.50,
            account_id="MYBANK_CHQ",
            category="Bills",
            subcategory="Utilities",
        )
        df = _groups_to_dataframe([original_group])
        recovered = build_groups_from_dataframe(df)

        assert len(recovered) == 1
        p = recovered[0].primary
        assert p.transaction_id == "abc1234567890000"
        assert p.description == "EXAMPLE UTILITY"
        assert p.amount == pytest.approx(-42.50)
        assert p.account_id == "MYBANK_CHQ"
