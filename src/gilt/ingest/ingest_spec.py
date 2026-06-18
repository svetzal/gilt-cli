from __future__ import annotations

import hashlib
import logging
import textwrap
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd

from gilt.ingest import (
    _detect_columns,
    _detect_rbc_overrides,
    build_groups_from_dataframe,
    build_normalization_plan,
    build_transaction_id,
    build_transactions_from_dataframe,
    find_missing_columns,
    infer_account_for_file,
    load_accounts_config,
    load_file,
    normalize_file,
)
from gilt.model.account import Account


def _write_csv(tmp_path: Path, content: str, filename: str = "test.csv") -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return p


def _write_yaml(tmp_path: Path, content: str, filename: str = "accounts.yml") -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return p


class DescribeLoadAccountsConfig:
    """Behaviour of load_accounts_config() YAML parsing."""

    def it_should_return_empty_list_for_missing_file(self, tmp_path):
        missing = tmp_path / "accounts.yml"
        result = load_accounts_config(missing)
        assert result == []

    def it_should_parse_minimal_account_entry(self, tmp_path):
        yml = _write_yaml(
            tmp_path,
            """\
            accounts:
              - account_id: MYBANK_CHQ
            """,
        )
        accounts = load_accounts_config(yml)
        assert len(accounts) == 1
        assert accounts[0].account_id == "MYBANK_CHQ"

    def it_should_parse_account_with_source_patterns(self, tmp_path):
        yml = _write_yaml(
            tmp_path,
            """\
            accounts:
              - account_id: MYBANK_CHQ
                source_patterns:
                  - "mybank-chequing*.csv"
                  - "mybank_chq*.csv"
            """,
        )
        accounts = load_accounts_config(yml)
        assert len(accounts) == 1
        assert accounts[0].source_patterns == ["mybank-chequing*.csv", "mybank_chq*.csv"]

    def it_should_parse_multiple_accounts(self, tmp_path):
        yml = _write_yaml(
            tmp_path,
            """\
            accounts:
              - account_id: MYBANK_CHQ
              - account_id: MYBANK_CC
              - account_id: BANK2_BIZ
            """,
        )
        accounts = load_accounts_config(yml)
        assert len(accounts) == 3
        ids = [a.account_id for a in accounts]
        assert "MYBANK_CHQ" in ids
        assert "BANK2_BIZ" in ids

    def it_should_return_empty_list_for_empty_yaml(self, tmp_path):
        yml = _write_yaml(tmp_path, "")
        result = load_accounts_config(yml)
        assert result == []


class DescribeInferAccountForFile:
    """Behaviour of infer_account_for_file() pattern matching."""

    def it_should_match_file_by_source_pattern(self):
        accounts = [
            Account(account_id="MYBANK_CHQ", source_patterns=["mybank-chequing*.csv"]),
            Account(account_id="MYBANK_CC", source_patterns=["mybank-credit*.csv"]),
        ]
        file_path = Path("/ingest/mybank-chequing-2025-01.csv")
        result = infer_account_for_file(accounts, file_path)
        assert result is not None
        assert result.account_id == "MYBANK_CHQ"

    def it_should_return_none_when_no_pattern_matches(self):
        accounts = [
            Account(account_id="MYBANK_CHQ", source_patterns=["mybank-chequing*.csv"]),
        ]
        file_path = Path("/ingest/otherbank-export.csv")
        result = infer_account_for_file(accounts, file_path)
        assert result is None

    def it_should_return_none_when_accounts_list_is_empty_and_no_heuristic_matches(self):
        result = infer_account_for_file([], Path("/ingest/unknown-export.csv"))
        assert result is None

    def it_should_match_first_account_with_matching_pattern(self):
        accounts = [
            Account(account_id="MYBANK_CHQ", source_patterns=["mybank*.csv"]),
            Account(account_id="MYBANK_CC", source_patterns=["mybank*.csv"]),
        ]
        file_path = Path("/ingest/mybank-export.csv")
        result = infer_account_for_file(accounts, file_path)
        # First match wins
        assert result is not None
        assert result.account_id == "MYBANK_CHQ"

    def it_should_match_account_with_multiple_patterns(self):
        accounts = [
            Account(
                account_id="MYBANK_CHQ",
                source_patterns=["mybank-chq*.csv", "mybank-chequing*.csv"],
            ),
        ]
        result = infer_account_for_file(
            accounts, Path("/ingest/mybank-chequing-jan.csv")
        )
        assert result is not None
        assert result.account_id == "MYBANK_CHQ"


class DescribePlanNormalization:
    """Behaviour of build_normalization_plan() file-to-account mapping."""

    def it_should_return_empty_plan_for_no_inputs(self, tmp_path):
        plan = build_normalization_plan([], tmp_path, [])
        assert plan == []

    def it_should_map_file_to_matched_account(self, tmp_path):
        accounts = [
            Account(account_id="MYBANK_CHQ", source_patterns=["mybank-chequing*.csv"]),
        ]
        files = [Path("/ingest/mybank-chequing-2025.csv")]
        plan = build_normalization_plan(files, tmp_path, accounts)
        assert len(plan) == 1
        assert plan[0][0] == Path("/ingest/mybank-chequing-2025.csv")
        assert plan[0][1] == "MYBANK_CHQ"

    def it_should_map_unrecognised_file_to_none(self, tmp_path):
        accounts = [
            Account(account_id="MYBANK_CHQ", source_patterns=["mybank*.csv"]),
        ]
        files = [Path("/ingest/unknown-bank-export.csv")]
        plan = build_normalization_plan(files, tmp_path, accounts)
        assert len(plan) == 1
        assert plan[0][1] is None

    def it_should_map_multiple_files_independently(self, tmp_path):
        accounts = [
            Account(account_id="MYBANK_CHQ", source_patterns=["mybank-chequing*.csv"]),
            Account(account_id="BANK2_BIZ", source_patterns=["bank2-biz*.csv"]),
        ]
        files = [
            Path("/ingest/mybank-chequing-jan.csv"),
            Path("/ingest/bank2-biz-jan.csv"),
            Path("/ingest/other-export.csv"),
        ]
        plan = build_normalization_plan(files, tmp_path, accounts)
        assert len(plan) == 3
        ids = {str(p): a_id for p, a_id in plan}
        assert ids["/ingest/mybank-chequing-jan.csv"] == "MYBANK_CHQ"
        assert ids["/ingest/bank2-biz-jan.csv"] == "BANK2_BIZ"
        assert ids["/ingest/other-export.csv"] is None


class DescribeBuildTransactionId:
    """Behaviour of build_transaction_id() SHA-256 hash."""

    def it_should_return_16_hex_character_string(self):
        txn_id = build_transaction_id("MYBANK_CHQ", "2025-01-15", -42.50, "SAMPLE STORE")
        assert len(txn_id) == 16
        assert all(c in "0123456789abcdef" for c in txn_id)

    def it_should_produce_deterministic_output_for_same_inputs(self):
        id1 = build_transaction_id("MYBANK_CHQ", "2025-01-15", -42.50, "SAMPLE STORE")
        id2 = build_transaction_id("MYBANK_CHQ", "2025-01-15", -42.50, "SAMPLE STORE")
        assert id1 == id2

    def it_should_produce_different_ids_for_different_accounts(self):
        id1 = build_transaction_id("MYBANK_CHQ", "2025-01-15", -42.50, "SAMPLE STORE")
        id2 = build_transaction_id("MYBANK_CC", "2025-01-15", -42.50, "SAMPLE STORE")
        assert id1 != id2

    def it_should_produce_different_ids_for_different_dates(self):
        id1 = build_transaction_id("MYBANK_CHQ", "2025-01-15", -42.50, "SAMPLE STORE")
        id2 = build_transaction_id("MYBANK_CHQ", "2025-01-16", -42.50, "SAMPLE STORE")
        assert id1 != id2

    def it_should_produce_different_ids_for_different_amounts(self):
        id1 = build_transaction_id("MYBANK_CHQ", "2025-01-15", -42.50, "SAMPLE STORE")
        id2 = build_transaction_id("MYBANK_CHQ", "2025-01-15", -43.00, "SAMPLE STORE")
        assert id1 != id2

    def it_should_produce_different_ids_for_different_descriptions(self):
        id1 = build_transaction_id("MYBANK_CHQ", "2025-01-15", -42.50, "SAMPLE STORE")
        id2 = build_transaction_id("MYBANK_CHQ", "2025-01-15", -42.50, "ACME CORP")
        assert id1 != id2

    def it_should_match_manually_computed_sha256_first_16_chars(self):
        account_id = "MYBANK_CHQ"
        txn_date = "2025-01-15"
        amount = -42.5
        description = "SAMPLE STORE"
        base = f"{account_id}|{txn_date}|{amount}|{description}"
        expected = hashlib.sha256(base.encode("utf-8")).hexdigest()[:16]
        result = build_transaction_id(account_id, txn_date, amount, description)
        assert result == expected


class DescribeParseFileAmountSign:
    """Amount sign handling during ingestion."""

    def it_should_keep_amounts_as_is_with_expenses_negative(self, tmp_path):
        csv = _write_csv(tmp_path, """\
            Date,Description,Amount
            2025-01-15,SAMPLE STORE,-42.50
            2025-01-20,DEPOSIT,100.00
        """)
        df = load_file(csv, "MYBANK_CHQ", amount_sign="expenses_negative")
        amounts = df["amount"].tolist()
        assert amounts[0] == -42.50
        assert amounts[1] == 100.00

    def it_should_negate_amounts_with_expenses_positive(self, tmp_path):
        csv = _write_csv(tmp_path, """\
            Date,Description,Amount
            2025-01-15,SAMPLE STORE,42.50
            2025-01-20,PAYMENT,-100.00
        """)
        df = load_file(csv, "MYBANK_CC", amount_sign="expenses_positive")
        amounts = df["amount"].tolist()
        assert amounts[0] == -42.50
        assert amounts[1] == 100.00

    def it_should_default_to_expenses_negative(self, tmp_path):
        csv = _write_csv(tmp_path, """\
            Date,Description,Amount
            2025-01-15,SAMPLE STORE,-42.50
        """)
        df = load_file(csv, "MYBANK_CHQ")
        assert df["amount"].iloc[0] == -42.50

    def it_should_negate_amounts_preserving_transaction_id_stability(self, tmp_path):
        """Transaction IDs use the final (negated) amount, ensuring idempotency."""
        csv = _write_csv(tmp_path, """\
            Date,Description,Amount
            2025-01-15,SAMPLE STORE,42.50
        """)
        df = load_file(csv, "MYBANK_CC", amount_sign="expenses_positive")
        # Re-parse should produce the same transaction_id
        df2 = load_file(csv, "MYBANK_CC", amount_sign="expenses_positive")
        assert df["transaction_id"].iloc[0] == df2["transaction_id"].iloc[0]


class DescribeNormalizeFileEventSourcing:
    def it_should_log_warning_when_description_observed_event_creation_fails(
        self, tmp_path, caplog
    ):
        input_path = _write_csv(
            tmp_path,
            """\
            date,description,amount,currency
            2025-01-15,NEW DESCRIPTION,-50.0,CAD
            """,
            filename="import.csv",
        )

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        existing_ledger = (
            "transaction_id,date,description,amount,currency,account_id,"
            "counterparty,category,subcategory,notes,source_file\n"
            "aaaa1234bbbb5678,2025-01-15,OLD DESCRIPTION,-50.0,CAD,MYBANK_CHQ,"
            ",,,,existing.csv\n"
        )
        (output_dir / "MYBANK_CHQ.csv").write_text(existing_ledger, encoding="utf-8")

        with (
            patch(
                "gilt.model.events.TransactionDescriptionObserved",
                side_effect=ValueError("test event creation failure"),
            ),
            caplog.at_level(logging.WARNING, logger="gilt.ingest"),
        ):
            normalize_file(input_path, "MYBANK_CHQ", output_dir, event_store=Mock())

        assert "Skipped TransactionDescriptionObserved" in caplog.text
        assert (output_dir / "MYBANK_CHQ.csv").exists()

    def it_should_log_warning_when_transaction_imported_event_creation_fails(
        self, tmp_path, caplog
    ):
        input_path = _write_csv(
            tmp_path,
            """\
            date,description,amount,currency
            2025-01-15,SAMPLE STORE,-50.0,CAD
            """,
            filename="import.csv",
        )

        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with (
            patch(
                "gilt.model.events.TransactionImported",
                side_effect=ValueError("test event creation failure"),
            ),
            caplog.at_level(logging.WARNING, logger="gilt.ingest"),
        ):
            normalize_file(input_path, "MYBANK_CHQ", output_dir, event_store=Mock())

        assert "Skipped TransactionImported" in caplog.text
        assert (output_dir / "MYBANK_CHQ.csv").exists()


class DescribeDetectColumns:
    """Behaviour of _detect_columns() column-role mapping."""

    def it_should_map_standard_columns_to_their_logical_roles(self):
        cols = ["Date", "Description", "Amount", "Currency"]

        result = _detect_columns(cols)

        assert result["date"] == "Date"
        assert result["desc1"] == "Description"
        assert result["desc2"] is None
        assert result["amount"] == "Amount"
        assert result["usd"] is None
        assert result["currency"] == "Currency"

    def it_should_map_rbc_style_columns(self):
        cols = [
            "Account Type",
            "Account Number",
            "Transaction Date",
            "Cheque Number",
            "Description 1",
            "Description 2",
            "CAD$",
            "USD$",
        ]

        result = _detect_columns(cols)

        assert result["date"] == "Transaction Date"
        assert result["desc1"] == "Description 1"
        assert result["desc2"] == "Description 2"
        assert result["amount"] == "CAD$"
        assert result["usd"] == "USD$"

    def it_should_return_none_for_all_roles_when_no_recognised_columns_present(self):
        cols = ["col_a", "col_b", "col_c"]

        result = _detect_columns(cols)

        assert result["date"] is None
        assert result["desc1"] is None
        assert result["desc2"] is None
        assert result["amount"] is None
        assert result["usd"] is None
        assert result["currency"] is None

    def it_should_match_column_names_case_insensitively(self):
        cols = ["DATE", "DESCRIPTION", "AMOUNT"]

        result = _detect_columns(cols)

        assert result["date"] == "DATE"
        assert result["desc1"] == "DESCRIPTION"
        assert result["amount"] == "AMOUNT"

    def it_should_prefer_cad_over_plain_amount(self):
        cols = ["Date", "Description", "Amount", "CAD$"]

        result = _detect_columns(cols)

        assert result["amount"] == "CAD$"


class DescribeDetectRbcOverrides:
    """Behaviour of _detect_rbc_overrides() RBC quirk detection."""

    def it_should_return_empty_dict_for_non_rbc_columns(self):
        df = pd.DataFrame({"Date": ["2025-01-15"], "Description": ["SAMPLE STORE"], "Amount": ["-42.50"]})
        cols = list(df.columns)

        result = _detect_rbc_overrides(df, cols)

        assert result == {}

    def it_should_return_empty_dict_when_rbc_columns_present_but_dates_not_shifted(self):
        df = pd.DataFrame({
            "Account Type": ["Chequing"],
            "Account Number": ["12345678"],
            "Transaction Date": ["1/15/2025"],
            "Cheque Number": [""],
            "Description 1": ["SAMPLE STORE"],
            "Description 2": [""],
            "CAD$": ["-42.50"],
            "USD$": [""],
        })
        cols = list(df.columns)

        result = _detect_rbc_overrides(df, cols)

        assert result == {}

    def it_should_return_override_series_when_rbc_date_shift_quirk_detected(self):
        df = pd.DataFrame({
            "Account Type": ["Chequing"],
            "Account Number": ["1/15/2025"],
            "Transaction Date": [""],
            "Cheque Number": ["REF1234ABCD"],
            "Description 1": ["SAMPLE STORE"],
            "Description 2": ["-42.50"],
            "CAD$": [""],
            "USD$": [""],
        })
        cols = list(df.columns)

        result = _detect_rbc_overrides(df, cols)

        assert "date_series" in result
        assert "desc1_series" in result
        assert "desc2_series" in result
        assert "amount_series" in result
        assert result["date_series"].iloc[0] == "1/15/2025"
        assert result["desc1_series"].iloc[0] == "REF1234ABCD"
        assert result["desc2_series"].iloc[0] == "SAMPLE STORE"
        assert result["amount_series"].iloc[0] == "-42.50"


class DescribeFindMissingColumns:
    """Pure-function tests for find_missing_columns — no DataFrame required."""

    def it_should_return_empty_list_when_all_required_columns_present(self):
        column_map = {"date": "Date", "desc1": "Description", "desc2": None, "amount": "CAD$", "usd": None}
        assert find_missing_columns(column_map, {}) == []

    def it_should_flag_missing_date_when_no_override(self):
        column_map = {"date": None, "desc1": "Description", "desc2": None, "amount": "CAD$", "usd": None}
        missing = find_missing_columns(column_map, {})
        assert "date" in missing

    def it_should_not_flag_date_when_date_series_override_present(self):
        column_map = {"date": None, "desc1": "Description", "desc2": None, "amount": "CAD$", "usd": None}
        import pandas as pd
        missing = find_missing_columns(column_map, {"date_series": pd.Series(["2025-01-01"])})
        assert "date" not in missing

    def it_should_flag_missing_description_when_no_desc_columns_or_overrides(self):
        column_map = {"date": "Date", "desc1": None, "desc2": None, "amount": "CAD$", "usd": None}
        missing = find_missing_columns(column_map, {})
        assert "description" in missing

    def it_should_not_flag_description_when_desc2_is_present(self):
        column_map = {"date": "Date", "desc1": None, "desc2": "Description 2", "amount": "CAD$", "usd": None}
        missing = find_missing_columns(column_map, {})
        assert "description" not in missing

    def it_should_flag_missing_amount_when_no_amount_usd_or_override(self):
        column_map = {"date": "Date", "desc1": "Description", "desc2": None, "amount": None, "usd": None}
        missing = find_missing_columns(column_map, {})
        assert "amount" in missing

    def it_should_not_flag_amount_when_usd_column_present(self):
        column_map = {"date": "Date", "desc1": "Description", "desc2": None, "amount": None, "usd": "USD$"}
        missing = find_missing_columns(column_map, {})
        assert "amount" not in missing

    def it_should_flag_all_three_when_all_are_missing(self):
        column_map = {"date": None, "desc1": None, "desc2": None, "amount": None, "usd": None}
        missing = find_missing_columns(column_map, {})
        assert set(missing) == {"date", "description", "amount"}


class DescribeBuildTransactionsFromDataframe:
    def _make_standard_df(self):
        return pd.DataFrame(
            [
                {
                    "transaction_id": "abc123def456789a",
                    "date": "2025-03-15",
                    "description": "SAMPLE STORE",
                    "amount": -42.00,
                    "currency": "CAD",
                    "account_id": "MYBANK_CHQ",
                    "counterparty": "SAMPLE STORE",
                    "category": None,
                    "subcategory": None,
                    "notes": None,
                    "source_file": "mybank_2025.csv",
                    "metadata": None,
                }
            ]
        )

    def it_should_build_transactions_from_a_standard_fields_dataframe(self):
        df = self._make_standard_df()
        transactions = build_transactions_from_dataframe(df)
        assert len(transactions) == 1
        t = transactions[0]
        assert t.transaction_id == "abc123def456789a"
        assert str(t.date) == "2025-03-15"
        assert t.description == "SAMPLE STORE"
        assert t.amount == -42.00
        assert t.currency == "CAD"
        assert t.account_id == "MYBANK_CHQ"
        assert t.source_file == "mybank_2025.csv"
        assert t.metadata == {}

    def it_should_convert_nan_counterparty_to_none(self):
        df = self._make_standard_df()
        df.at[0, "counterparty"] = float("nan")
        transactions = build_transactions_from_dataframe(df)
        assert transactions[0].counterparty is None

    def it_should_build_groups_with_matching_group_id(self):
        df = self._make_standard_df()
        groups = build_groups_from_dataframe(df)
        assert len(groups) == 1
        assert groups[0].group_id == groups[0].primary.transaction_id

    def it_should_return_empty_list_for_empty_dataframe(self):
        from gilt.model.ledger_io import STANDARD_FIELDS

        df = pd.DataFrame(columns=STANDARD_FIELDS)
        transactions = build_transactions_from_dataframe(df)
        assert transactions == []
