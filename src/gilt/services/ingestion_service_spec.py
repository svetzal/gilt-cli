"""
Tests for ingestion service.

Tests file discovery, account matching, and ingestion planning logic
without UI dependencies.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from gilt.model.account import Account
from gilt.services.ingestion_service import IngestionPlan, IngestionService


class DescribeIngestionService:
    """Tests for IngestionService class."""

    @pytest.fixture
    def accounts_config(self) -> list[Account]:
        """Return sample accounts configuration."""
        return [
            Account(
                account_id="MYBANK_CHQ",
                institution="MyBank",
                product="Chequing",
                currency="CAD",
                source_patterns=["*mybank*chequing*.csv"],
            ),
            Account(
                account_id="BANK2_BIZ",
                institution="SecondBank",
                product="Business",
                currency="CAD",
                source_patterns=["*bank2*business*.csv"],
            ),
            Account(
                account_id="BANK2_LOC",
                institution="SecondBank",
                product="Line of Credit",
                currency="CAD",
                source_patterns=["*bank2*line*.csv"],
            ),
            Account(
                account_id="MYBANK_CC",
                institution="MyBank",
                product="Credit Card",
                currency="CAD",
                source_patterns=["*mybank*cc*.csv", "*mybank*creditcard*.csv"],
            ),
        ]

    @pytest.fixture
    def service(self, accounts_config: list[Account]) -> IngestionService:
        """Return ingestion service with sample config."""
        return IngestionService(accounts=accounts_config)

    @pytest.fixture
    def ingest_dir_with_files(self, tmp_path: Path) -> Path:
        """Create temporary ingest directory with sample CSV files."""
        ingest_dir = tmp_path / "ingest"
        ingest_dir.mkdir()

        # Create sample files
        (ingest_dir / "2025-01-01-mybank-chequing.csv").write_text("test")
        (ingest_dir / "2025-01-01-bank2-business.csv").write_text("test")
        (ingest_dir / "2025-01-01-bank2-line.csv").write_text("test")
        (ingest_dir / "2025-01-01-mybank-cc.csv").write_text("test")
        (ingest_dir / "unknown-bank.csv").write_text("test")

        return ingest_dir


class DescribeDiscoverInputs(DescribeIngestionService):
    """Tests for discover_inputs method."""

    def it_should_discover_files_matching_configured_patterns(
        self, service: IngestionService, ingest_dir_with_files: Path
    ):
        """Should discover files that match configured account patterns."""
        inputs = service.discover_inputs(ingest_dir_with_files)

        # Should find 4 files that match patterns (exclude unknown-bank.csv)
        assert len(inputs) == 4
        assert all(p.suffix == ".csv" for p in inputs)

        # Check specific matches
        file_names = [p.name for p in inputs]
        assert "2025-01-01-mybank-chequing.csv" in file_names
        assert "2025-01-01-bank2-business.csv" in file_names
        assert "2025-01-01-bank2-line.csv" in file_names
        assert "2025-01-01-mybank-cc.csv" in file_names
        assert "unknown-bank.csv" not in file_names

    def it_should_discover_all_csv_when_no_patterns_configured(
        self, ingest_dir_with_files: Path
    ):
        """Should discover all CSV files when no patterns are configured."""
        service = IngestionService(accounts=[])
        inputs = service.discover_inputs(ingest_dir_with_files)

        # Should find all 5 CSV files
        assert len(inputs) == 5
        file_names = [p.name for p in inputs]
        assert "unknown-bank.csv" in file_names

    def it_should_return_empty_list_for_nonexistent_directory(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should return empty list when directory doesn't exist."""
        nonexistent_dir = tmp_path / "does-not-exist"
        inputs = service.discover_inputs(nonexistent_dir)
        assert inputs == []

    def it_should_return_empty_list_for_empty_directory(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should return empty list when directory is empty."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()
        inputs = service.discover_inputs(empty_dir)
        assert inputs == []

    def it_should_return_sorted_results(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should return files in sorted order."""
        ingest_dir = tmp_path / "ingest"
        ingest_dir.mkdir()

        # Create files in non-alphabetical order
        (ingest_dir / "z-mybank-chequing.csv").write_text("test")
        (ingest_dir / "a-mybank-chequing.csv").write_text("test")
        (ingest_dir / "m-mybank-chequing.csv").write_text("test")

        inputs = service.discover_inputs(ingest_dir)
        names = [p.name for p in inputs]

        assert names == sorted(names)

    def it_should_handle_multiple_patterns_per_account(
        self, tmp_path: Path
    ):
        """Should discover files matching any pattern for an account."""
        ingest_dir = tmp_path / "ingest"
        ingest_dir.mkdir()

        (ingest_dir / "mybank-cc.csv").write_text("test")
        (ingest_dir / "mybank-creditcard.csv").write_text("test")

        accounts = [
            Account(
                account_id="MYBANK_CC",
                source_patterns=["*mybank-cc*.csv", "*mybank-creditcard*.csv"],
            )
        ]
        service = IngestionService(accounts=accounts)

        inputs = service.discover_inputs(ingest_dir)
        assert len(inputs) == 2

    def it_should_deduplicate_files_matching_multiple_patterns(
        self, tmp_path: Path
    ):
        """Should only include each file once if it matches multiple patterns."""
        ingest_dir = tmp_path / "ingest"
        ingest_dir.mkdir()

        (ingest_dir / "mybank-chequing.csv").write_text("test")

        accounts = [
            Account(
                account_id="TEST",
                source_patterns=["*mybank*.csv", "*chequing*.csv"],
            )
        ]
        service = IngestionService(accounts=accounts)

        inputs = service.discover_inputs(ingest_dir)
        assert len(inputs) == 1  # Not 2, even though file matches both patterns


class DescribeMatchFileToAccount(DescribeIngestionService):
    """Tests for match_file_to_account method."""

    def it_should_match_file_to_configured_account_by_pattern(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should match file to account using configured pattern."""
        file_path = tmp_path / "2025-01-01-mybank-chequing.csv"
        account_id = service.match_file_to_account(file_path)
        assert account_id == "MYBANK_CHQ"

    def it_should_match_file_case_insensitively(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should match file patterns case-insensitively."""
        file_path = tmp_path / "2025-01-01-MYBANK-CHEQUING.csv"
        account_id = service.match_file_to_account(file_path)
        assert account_id == "MYBANK_CHQ"

    def it_should_match_multiple_patterns_for_same_account(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should match file using any of the account's patterns."""
        # MYBANK_CC has patterns for both "cc" and "creditcard"
        cc_file = tmp_path / "mybank-cc.csv"
        assert service.match_file_to_account(cc_file) == "MYBANK_CC"

        creditcard_file = tmp_path / "mybank-creditcard.csv"
        assert service.match_file_to_account(creditcard_file) == "MYBANK_CC"

    def it_should_return_none_when_no_config_patterns_match(
        self, tmp_path: Path
    ):
        """Should return None when no configured patterns match."""
        service = IngestionService(accounts=[])

        file_path = tmp_path / "some-bank-chequing.csv"
        assert service.match_file_to_account(file_path) is None

    def it_should_return_none_when_no_match_found(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should return None when file can't be matched to any account."""
        file_path = tmp_path / "unknown-bank.csv"
        account_id = service.match_file_to_account(file_path)
        assert account_id is None

    def it_should_match_first_pattern_when_multiple_accounts_match(
        self, tmp_path: Path
    ):
        """Should return first matching account when multiple accounts could match."""
        # Create two accounts with overlapping patterns
        accounts = [
            Account(account_id="FIRST", source_patterns=["*test*.csv"]),
            Account(account_id="SECOND", source_patterns=["*test*.csv"]),
        ]
        service = IngestionService(accounts=accounts)

        file_path = tmp_path / "test-file.csv"
        account_id = service.match_file_to_account(file_path)

        # Should match first account in list
        assert account_id == "FIRST"


class DescribePlanIngestion(DescribeIngestionService):
    """Tests for plan_ingestion method."""

    def it_should_create_complete_ingestion_plan(
        self, service: IngestionService, ingest_dir_with_files: Path
    ):
        """Should create plan mapping all discovered files to accounts."""
        plan = service.plan_ingestion(ingest_dir_with_files)

        assert isinstance(plan, IngestionPlan)
        assert plan.total_files == 4  # Excludes unknown-bank.csv
        assert len(plan.files) == 4
        assert len(plan.unmatched) == 0

    def it_should_track_unmatched_files(self, tmp_path: Path):
        """Should track files that couldn't be matched to any account."""
        ingest_dir = tmp_path / "ingest"
        ingest_dir.mkdir()

        (ingest_dir / "mybank-chequing.csv").write_text("test")
        (ingest_dir / "unknown-bank.csv").write_text("test")
        (ingest_dir / "another-unknown.csv").write_text("test")

        accounts = [
            Account(account_id="MYBANK_CHQ", source_patterns=["*mybank*chequing*.csv"])
        ]
        service = IngestionService(accounts=accounts)

        plan = service.plan_ingestion(ingest_dir)

        assert plan.total_files == 1  # Only matches pattern
        assert len(plan.files) == 1
        assert len(plan.unmatched) == 0
        assert plan.files[0][1] == "MYBANK_CHQ"

    def it_should_map_files_to_correct_accounts(
        self, service: IngestionService, ingest_dir_with_files: Path
    ):
        """Should correctly map each file to its target account."""
        plan = service.plan_ingestion(ingest_dir_with_files)

        file_mapping = {p.name: acct_id for p, acct_id in plan.files}

        assert file_mapping["2025-01-01-mybank-chequing.csv"] == "MYBANK_CHQ"
        assert file_mapping["2025-01-01-bank2-business.csv"] == "BANK2_BIZ"
        assert file_mapping["2025-01-01-bank2-line.csv"] == "BANK2_LOC"
        assert file_mapping["2025-01-01-mybank-cc.csv"] == "MYBANK_CC"

    def it_should_handle_empty_directory(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should handle empty directory gracefully."""
        empty_dir = tmp_path / "empty"
        empty_dir.mkdir()

        plan = service.plan_ingestion(empty_dir)

        assert plan.total_files == 0
        assert plan.files == []
        assert plan.unmatched == []

    def it_should_handle_all_unmatched_files(self, tmp_path: Path):
        """Should handle case where no files match any account."""
        ingest_dir = tmp_path / "ingest"
        ingest_dir.mkdir()

        (ingest_dir / "unknown1.csv").write_text("test")
        (ingest_dir / "unknown2.csv").write_text("test")

        service = IngestionService(accounts=[])
        plan = service.plan_ingestion(ingest_dir)

        assert plan.total_files == 2
        assert len(plan.files) == 2
        assert len(plan.unmatched) == 2
        assert all(acct_id is None for _, acct_id in plan.files)

    def it_should_preserve_file_order(
        self, service: IngestionService, tmp_path: Path
    ):
        """Should preserve sorted order of files in plan."""
        ingest_dir = tmp_path / "ingest"
        ingest_dir.mkdir()

        # Create files in non-alphabetical order
        (ingest_dir / "z-mybank-chequing.csv").write_text("test")
        (ingest_dir / "a-mybank-chequing.csv").write_text("test")
        (ingest_dir / "m-mybank-chequing.csv").write_text("test")

        plan = service.plan_ingestion(ingest_dir)
        file_names = [p.name for p in (f for f, _ in plan.files)]

        assert file_names == sorted(file_names)
