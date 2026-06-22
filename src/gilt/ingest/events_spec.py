"""Specs for gilt.ingest.events — event emission side effects."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, call

import pandas as pd
import pytest

from gilt.ingest.events import (
    _emit_description_observed_event,
    _emit_transaction_events,
    _emit_transaction_imported_event,
)
from gilt.model.events import TransactionDescriptionObserved, TransactionImported


def _make_store() -> MagicMock:
    return MagicMock()


def _make_row(txn_id: str = "abc1234567890000", date: str = "2024-01-15",
              description: str = "EXAMPLE UTILITY", amount: float = -42.50,
              currency: str = "CAD", account_id: str = "MYBANK_CHQ") -> pd.Series:
    return pd.Series({
        "transaction_id": txn_id,
        "date": date,
        "description": description,
        "amount": amount,
        "currency": currency,
        "account_id": account_id,
    })


class DescribeEmitTransactionImportedEvent:
    def it_should_emit_event_for_new_transaction(self):
        store = _make_store()
        row = _make_row()
        _emit_transaction_imported_event(
            store, row, "abc1234567890000", existing_ids=set(),
            input_path=Path("mybank.csv"), account_id="MYBANK_CHQ"
        )
        store.append_event.assert_called_once()
        event = store.append_event.call_args[0][0]
        assert isinstance(event, TransactionImported)
        assert event.transaction_id == "abc1234567890000"

    def it_should_not_emit_event_when_transaction_already_exists(self):
        store = _make_store()
        row = _make_row()
        _emit_transaction_imported_event(
            store, row, "abc1234567890000", existing_ids={"abc1234567890000"},
            input_path=Path("mybank.csv"), account_id="MYBANK_CHQ"
        )
        store.append_event.assert_not_called()

    def it_should_not_emit_event_for_invalid_amount(self):
        store = _make_store()
        row = _make_row(amount=float("nan"))
        # NaN amount causes ValueError in Decimal conversion
        _emit_transaction_imported_event(
            store, row, "abc1234567890000", existing_ids=set(),
            input_path=Path("mybank.csv"), account_id="MYBANK_CHQ"
        )
        store.append_event.assert_not_called()


class DescribeEmitDescriptionObservedEvent:
    def it_should_emit_event_when_description_changed(self):
        store = _make_store()
        row = _make_row(txn_id="new0000000000000", description="NEW DESC")
        key = ("2024-01-15", "-42.5", "MYBANK_CHQ")
        existing_by_key = {key: ("orig000000000000", "OLD DESC")}
        _emit_description_observed_event(
            store, row, key, existing_by_key,
            txn_id="new0000000000000",
            input_path=Path("mybank.csv"),
            account_id="MYBANK_CHQ",
        )
        store.append_event.assert_called_once()
        event = store.append_event.call_args[0][0]
        assert isinstance(event, TransactionDescriptionObserved)
        assert event.new_description == "NEW DESC"
        assert event.original_description == "OLD DESC"

    def it_should_not_emit_event_when_key_not_in_existing(self):
        store = _make_store()
        row = _make_row()
        _emit_description_observed_event(
            store, row, ("2024-01-15", "-42.5", "MYBANK_CHQ"), existing_by_key={},
            txn_id="abc1234567890000",
            input_path=Path("mybank.csv"),
            account_id="MYBANK_CHQ",
        )
        store.append_event.assert_not_called()

    def it_should_not_emit_event_when_description_unchanged(self):
        store = _make_store()
        row = _make_row(description="SAME DESC")
        key = ("2024-01-15", "-42.5", "MYBANK_CHQ")
        existing_by_key = {key: ("abc1234567890000", "SAME DESC")}
        _emit_description_observed_event(
            store, row, key, existing_by_key,
            txn_id="abc1234567890000",
            input_path=Path("mybank.csv"),
            account_id="MYBANK_CHQ",
        )
        store.append_event.assert_not_called()


class DescribeEmitTransactionEvents:
    def it_should_emit_imported_events_for_new_transactions(self):
        store = _make_store()
        out_df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": "2024-01-15",
            "description": "EXAMPLE UTILITY",
            "amount": -42.50,
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
        }])
        existing_df = pd.DataFrame(columns=["transaction_id", "date", "amount",
                                            "account_id", "description"])
        _emit_transaction_events(
            out_df, existing_df, store, Path("mybank.csv"), "MYBANK_CHQ"
        )
        assert store.append_event.call_count == 1
        event = store.append_event.call_args[0][0]
        assert isinstance(event, TransactionImported)

    def it_should_skip_rows_with_nan_amounts(self):
        store = _make_store()
        out_df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": "2024-01-15",
            "description": "EXAMPLE UTILITY",
            "amount": float("nan"),
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
        }])
        existing_df = pd.DataFrame(columns=["transaction_id", "date", "amount",
                                            "account_id", "description"])
        _emit_transaction_events(
            out_df, existing_df, store, Path("mybank.csv"), "MYBANK_CHQ"
        )
        store.append_event.assert_not_called()

    def it_should_skip_rows_with_nan_date(self):
        store = _make_store()
        out_df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": float("nan"),
            "description": "EXAMPLE UTILITY",
            "amount": -42.50,
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
        }])
        existing_df = pd.DataFrame(columns=["transaction_id", "date", "amount",
                                            "account_id", "description"])
        _emit_transaction_events(
            out_df, existing_df, store, Path("mybank.csv"), "MYBANK_CHQ"
        )
        store.append_event.assert_not_called()

    def it_should_not_emit_imported_for_existing_transaction(self):
        store = _make_store()
        out_df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": "2024-01-15",
            "description": "EXAMPLE UTILITY",
            "amount": -42.50,
            "currency": "CAD",
            "account_id": "MYBANK_CHQ",
        }])
        existing_df = pd.DataFrame([{
            "transaction_id": "abc1234567890000",
            "date": "2024-01-15",
            "amount": -42.50,
            "account_id": "MYBANK_CHQ",
            "description": "EXAMPLE UTILITY",
        }])
        _emit_transaction_events(
            out_df, existing_df, store, Path("mybank.csv"), "MYBANK_CHQ"
        )
        store.append_event.assert_not_called()
