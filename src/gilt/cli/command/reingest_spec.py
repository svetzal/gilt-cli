from __future__ import annotations

"""
Specs for the reingest CLI command.

These tests verify command-level behavior (dry-run, account not found, no files).
The purge logic (collect/execute) is tested in reingestion_service_spec.py.
"""

from pathlib import Path
from unittest.mock import MagicMock, patch

from gilt.cli.command.reingest import (
    _delete_existing_ledger,
    _finalize_reingest,
    _reingest_source_files,
    run,
)
from gilt.workspace import Workspace


class DescribeDeleteExistingLedger:
    """Specs for _delete_existing_ledger()."""

    def it_should_return_true_and_remove_file_when_ledger_exists(self, tmp_path: Path):
        ledger = tmp_path / "MYBANK_CHQ.csv"
        ledger.write_text("data", encoding="utf-8")

        result = _delete_existing_ledger(ledger)

        assert result is True
        assert not ledger.exists()

    def it_should_return_false_when_ledger_does_not_exist(self, tmp_path: Path):
        ledger = tmp_path / "MISSING.csv"

        result = _delete_existing_ledger(ledger)

        assert result is False


class DescribeReingestSourceFiles:
    """Specs for _reingest_source_files()."""

    def it_should_normalize_each_file_and_return_written_count(self, tmp_path: Path):
        ingestion_service = MagicMock()
        ingestion_service.amount_sign_for.return_value = -1
        event_store = MagicMock()
        out_path = tmp_path / "MYBANK_CHQ.csv"

        account_files = [(tmp_path / "export.csv", "MYBANK_CHQ")]

        with patch("gilt.cli.command.reingest.normalize_file", return_value=out_path):
            written, errors, written_paths = _reingest_source_files(
                account_files, ingestion_service, "MYBANK_CHQ", tmp_path, event_store
            )

        assert written == 1
        assert errors == []
        assert written_paths == [out_path]

    def it_should_collect_errors_without_stopping_on_individual_file_failure(self, tmp_path: Path):
        ingestion_service = MagicMock()
        ingestion_service.amount_sign_for.return_value = -1
        event_store = MagicMock()

        account_files = [
            (tmp_path / "export1.csv", "MYBANK_CHQ"),
            (tmp_path / "export2.csv", "MYBANK_CHQ"),
        ]

        with patch("gilt.cli.command.reingest.normalize_file", side_effect=OSError("read error")):
            written, errors, written_paths = _reingest_source_files(
                account_files, ingestion_service, "MYBANK_CHQ", tmp_path, event_store
            )

        assert written == 0
        assert len(errors) == 2
        assert written_paths == []

    def it_should_return_empty_results_for_empty_file_list(self, tmp_path: Path):
        ingestion_service = MagicMock()
        ingestion_service.amount_sign_for.return_value = -1
        event_store = MagicMock()

        written, errors, written_paths = _reingest_source_files(
            [], ingestion_service, "MYBANK_CHQ", tmp_path, event_store
        )

        assert written == 0
        assert errors == []
        assert written_paths == []


class DescribeFinalizeReingest:
    """Specs for _finalize_reingest()."""

    def it_should_link_transfers_and_rebuild_projections(self, tmp_path: Path):
        projection_builder = MagicMock()
        projection_builder.rebuild_from_scratch.return_value = 42
        event_store = MagicMock()

        with patch("gilt.cli.command.reingest.link_transfers", return_value=3) as mock_link:
            modified, events_processed = _finalize_reingest(tmp_path, projection_builder, event_store)

        mock_link.assert_called_once_with(processed_dir=tmp_path, write=True)
        projection_builder.rebuild_from_scratch.assert_called_once_with(event_store)
        assert modified == 3
        assert events_processed == 42


class DescribeReingestRunDryRun:
    """Specs for the reingest command run() in dry-run mode."""

    def it_should_return_one_when_account_not_in_config(self, tmp_path: Path):
        """Should return exit code 1 when the given account is not in config."""
        ws = Workspace(root=tmp_path)
        ws.accounts_config.parent.mkdir(parents=True, exist_ok=True)
        ws.accounts_config.write_text(
            "accounts: []\n",
            encoding="utf-8",
        )
        ws.ingest_dir.mkdir(parents=True, exist_ok=True)

        result = run(account="NONEXISTENT", workspace=ws, write=False)
        assert result == 1

    def it_should_return_one_when_no_source_files_match_account(self, tmp_path: Path):
        ws = Workspace(root=tmp_path)
        ws.accounts_config.parent.mkdir(parents=True, exist_ok=True)
        ws.accounts_config.write_text(
            "accounts:\n  - account_id: MYBANK_CHQ\n    source_patterns: ['*.csv']\n",
            encoding="utf-8",
        )
        ws.ingest_dir.mkdir(parents=True, exist_ok=True)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)

        mock_plan = MagicMock()
        mock_plan.files = []

        with patch("gilt.cli.command.reingest.IngestionService") as MockSvc:
            MockSvc.return_value.plan_ingestion.return_value = mock_plan
            result = run(account="MYBANK_CHQ", workspace=ws, write=False)

        assert result == 1

    def it_should_display_plan_and_return_zero_in_dry_run_mode(self, tmp_path: Path):
        ws = Workspace(root=tmp_path)
        ws.accounts_config.parent.mkdir(parents=True, exist_ok=True)
        ws.accounts_config.write_text(
            "accounts:\n  - account_id: MYBANK_CHQ\n    source_patterns: ['*.csv']\n",
            encoding="utf-8",
        )
        ws.ingest_dir.mkdir(parents=True, exist_ok=True)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)

        mock_plan = MagicMock()
        mock_plan.files = [(tmp_path / "export.csv", "MYBANK_CHQ")]
        mock_purge_plan = MagicMock()
        mock_purge_plan.event_ids = []
        mock_purge_plan.transaction_ids = []
        mock_ready = MagicMock()
        mock_ready.event_store = MagicMock()
        mock_ready.projection_builder = MagicMock()

        with (
            patch("gilt.cli.command.reingest.IngestionService") as MockSvc,
            patch("gilt.cli.command.reingest.require_event_sourcing", return_value=mock_ready),
            patch("gilt.cli.command.reingest.ReingestionService") as MockReingestSvc,
        ):
            MockSvc.return_value.plan_ingestion.return_value = mock_plan
            MockReingestSvc.return_value.plan_purge.return_value = mock_purge_plan

            result = run(account="MYBANK_CHQ", workspace=ws, write=False)

        assert result == 0
