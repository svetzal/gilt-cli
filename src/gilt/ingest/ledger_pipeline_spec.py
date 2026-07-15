"""Specs for gilt.ingest.ledger_pipeline — CSV reading and ledger merge."""

from __future__ import annotations

import textwrap
from pathlib import Path

import pandas as pd
import pytest

from gilt.ingest.ledger_pipeline import _merge_with_existing_ledger, load_file
from gilt.model.ledger_io import STANDARD_FIELDS, dump_ledger_csv
from gilt.testing import make_group, make_transaction


def _write_csv(tmp_path: Path, content: str, filename: str = "mybank.csv") -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return p


class DescribeLoadFile:
    def it_should_return_standard_fields_dataframe(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            Date,Description,Amount
            2024-01-15,EXAMPLE UTILITY,-42.50
        """)
        result = load_file(csv_path, "MYBANK_CHQ")
        for col in STANDARD_FIELDS:
            assert col in result.columns

    def it_should_compute_transaction_id(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            Date,Description,Amount
            2024-01-15,EXAMPLE UTILITY,-42.50
        """)
        result = load_file(csv_path, "MYBANK_CHQ")
        assert result.iloc[0]["transaction_id"] != ""
        assert len(result.iloc[0]["transaction_id"]) == 16

    def it_should_sort_output_by_date_amount_description(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            Date,Description,Amount
            2024-03-01,SAMPLE STORE,-5.00
            2024-01-15,EXAMPLE UTILITY,-42.50
        """)
        result = load_file(csv_path, "MYBANK_CHQ")
        assert result.iloc[0]["date"] <= result.iloc[1]["date"]

    def it_should_raise_value_error_for_missing_required_columns(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            SomeCol,OtherCol
            foo,bar
        """)
        with pytest.raises(ValueError, match="Missing required columns"):
            load_file(csv_path, "MYBANK_CHQ")

    def it_should_set_account_id_from_parameter(self, tmp_path):
        csv_path = _write_csv(tmp_path, """\
            Date,Description,Amount
            2024-01-15,ACME CORP,-10.00
        """)
        result = load_file(csv_path, "BANK2_BIZ")
        assert result.iloc[0]["account_id"] == "BANK2_BIZ"


class DescribeMergeWithExistingLedger:
    def _make_df(self, txn_id: str, date: str = "2024-01-15",
                 description: str = "EXAMPLE UTILITY", amount: float = -42.50,
                 account_id: str = "MYBANK_CHQ") -> pd.DataFrame:
        return pd.DataFrame([{
            "transaction_id": txn_id,
            "date": date,
            "description": description,
            "amount": amount,
            "currency": "CAD",
            "account_id": account_id,
            "counterparty": description,
            "category": None,
            "subcategory": None,
            "notes": None,
            "source_file": "mybank.csv",
        }])

    def it_should_return_new_rows_when_no_existing_ledger(self, tmp_path):
        new_df = self._make_df("abc1234567890000")
        ledger_path = tmp_path / "MYBANK_CHQ.csv"
        combined, existing = _merge_with_existing_ledger(new_df, ledger_path)
        assert len(combined) == 1
        assert len(existing) == 0

    def it_should_deduplicate_rows_with_same_transaction_id(self, tmp_path):
        # Write an existing ledger with one transaction
        ledger_dir = tmp_path
        txn = make_transaction(
            transaction_id="abc1234567890000",
            date="2024-01-15",
            description="EXAMPLE UTILITY",
            amount=-42.50,
            currency="CAD",
            account_id="MYBANK_CHQ",
            metadata={},
        )
        group = make_group(primary=txn)
        ledger_path = ledger_dir / "MYBANK_CHQ.csv"
        ledger_path.write_text(dump_ledger_csv([group]), encoding="utf-8")

        new_df = self._make_df("abc1234567890000")
        combined, existing = _merge_with_existing_ledger(new_df, ledger_path)
        count = (combined["transaction_id"] == "abc1234567890000").sum()
        assert count == 1

    def it_should_add_new_rows_not_present_in_existing_ledger(self, tmp_path):
        txn = make_transaction(
            transaction_id="abc1234567890000",
            date="2024-01-15",
            description="EXAMPLE UTILITY",
            amount=-42.50,
            currency="CAD",
            account_id="MYBANK_CHQ",
            metadata={},
        )
        group = make_group(primary=txn)
        ledger_path = tmp_path / "MYBANK_CHQ.csv"
        ledger_path.write_text(dump_ledger_csv([group]), encoding="utf-8")

        new_df = self._make_df("def9876543210000", description="SAMPLE STORE", amount=-5.00)
        combined, existing = _merge_with_existing_ledger(new_df, ledger_path)
        ids = set(combined["transaction_id"].astype(str))
        assert "abc1234567890000" in ids
        assert "def9876543210000" in ids
