"""Specs for gilt.ingest.account_matching — pure account inference logic."""

from __future__ import annotations

from pathlib import Path

from gilt.ingest.account_matching import build_normalization_plan, infer_account_for_file
from gilt.model.account import Account


def _account(account_id: str, patterns: list[str] | None = None) -> Account:
    return Account(account_id=account_id, source_patterns=patterns)


class DescribeInferAccountForFile:
    def it_should_match_by_source_pattern_glob(self):
        accounts = [_account("MYBANK_CHQ", ["mybank-chequing*.csv"])]
        result = infer_account_for_file(accounts, Path("mybank-chequing-2024.csv"))
        assert result is not None
        assert result.account_id == "MYBANK_CHQ"

    def it_should_match_first_account_with_matching_pattern(self):
        accounts = [
            _account("MYBANK_CHQ", ["mybank-chequing*.csv"]),
            _account("BANK2_BIZ", ["bank2-business*.csv"]),
        ]
        result = infer_account_for_file(accounts, Path("bank2-business-jan.csv"))
        assert result is not None
        assert result.account_id == "BANK2_BIZ"

    def it_should_return_none_when_no_pattern_matches_and_no_heuristic(self):
        accounts = [_account("MYBANK_CHQ", ["mybank*.csv"])]
        result = infer_account_for_file(accounts, Path("unknownbank_export.csv"))
        assert result is None

    def it_should_use_rbc_chq_heuristic_when_no_config(self):
        result = infer_account_for_file([], Path("rbc-chequing-2024.csv"))
        assert result is not None
        assert result.account_id == "RBC_CHQ"

    def it_should_use_scotia_curr_heuristic_when_no_config(self):
        result = infer_account_for_file([], Path("scotia-current-account.csv"))
        assert result is not None
        assert result.account_id == "SCOTIA_CURR"

    def it_should_use_scotia_loc_heuristic_when_no_config(self):
        result = infer_account_for_file([], Path("scotia-line-of-credit.csv"))
        assert result is not None
        assert result.account_id == "SCOTIA_LOC"

    def it_should_prefer_config_pattern_over_heuristic(self):
        accounts = [_account("MYBANK_CHQ", ["*rbc*.csv"])]
        result = infer_account_for_file(accounts, Path("rbc-chequing-2024.csv"))
        assert result is not None
        assert result.account_id == "MYBANK_CHQ"

    def it_should_return_none_when_no_accounts_and_no_heuristic_match(self):
        result = infer_account_for_file([], Path("unknown-export.csv"))
        assert result is None


class DescribeBuildNormalizationPlan:
    def it_should_return_one_entry_per_input_file(self):
        inputs = [Path("mybank-chequing.csv"), Path("bank2-business.csv")]
        accounts = [
            _account("MYBANK_CHQ", ["mybank*.csv"]),
            _account("BANK2_BIZ", ["bank2*.csv"]),
        ]
        plan = build_normalization_plan(inputs, Path("data/accounts"), accounts)
        assert len(plan) == 2

    def it_should_pair_each_path_with_inferred_account_id(self):
        inputs = [Path("mybank-chequing.csv")]
        accounts = [_account("MYBANK_CHQ", ["mybank*.csv"])]
        plan = build_normalization_plan(inputs, Path("data/accounts"), accounts)
        assert plan[0] == (Path("mybank-chequing.csv"), "MYBANK_CHQ")

    def it_should_pair_unmatched_files_with_none(self):
        inputs = [Path("unknown-export.csv")]
        accounts = [_account("MYBANK_CHQ", ["mybank*.csv"])]
        plan = build_normalization_plan(inputs, Path("data/accounts"), accounts)
        assert plan[0] == (Path("unknown-export.csv"), None)

    def it_should_preserve_input_order(self):
        inputs = [Path("b.csv"), Path("a.csv")]
        accounts = [
            _account("MYBANK_CHQ", ["a.csv"]),
            _account("BANK2_BIZ", ["b.csv"]),
        ]
        plan = build_normalization_plan(inputs, Path("data/accounts"), accounts)
        assert plan[0][0] == Path("b.csv")
        assert plan[1][0] == Path("a.csv")
