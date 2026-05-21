"""
Specs for IngestionOrchestrationService.

Privacy: all data is synthetic — no real bank names, account IDs, or merchant names.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from gilt.services.event_sourcing_service import EventSourcingService
from gilt.services.ingestion_orchestration_service import (
    IngestionOrchestrationService,
    PostIngestResult,
)
from gilt.storage.event_store import EventStore
from gilt.storage.projection import ProjectionBuilder
from gilt.workspace import Workspace


class DescribeIngestionOrchestrationService:
    @pytest.fixture
    def workspace(self, tmp_path: Path) -> Workspace:
        ws = Workspace(root=tmp_path)
        ws.ledger_data_dir.mkdir(parents=True, exist_ok=True)
        return ws

    @pytest.fixture
    def service(self, workspace: Workspace) -> IngestionOrchestrationService:
        return IngestionOrchestrationService(workspace)

    @pytest.fixture
    def output_dir(self, tmp_path: Path) -> Path:
        d = tmp_path / "accounts"
        d.mkdir(parents=True, exist_ok=True)
        return d

    @pytest.fixture
    def mock_event_store(self) -> Mock:
        store = Mock(spec=EventStore)
        store.get_latest_sequence_number.return_value = 42
        return store

    @pytest.fixture
    def mock_projection_builder(self) -> Mock:
        builder = Mock(spec=ProjectionBuilder)
        builder.get_all_transactions.return_value = []
        return builder

    @pytest.fixture
    def mock_es_service(self, mock_projection_builder: Mock) -> Mock:
        svc = Mock(spec=EventSourcingService)
        svc.get_projection_builder.return_value = mock_projection_builder
        svc.ensure_projections_up_to_date.return_value = 5
        return svc

    class DescribeRunPostIngest:
        def it_should_return_summary_with_transfer_and_event_counts(
            self,
            service: IngestionOrchestrationService,
            output_dir: Path,
            mock_event_store: Mock,
            mock_es_service: Mock,
            mock_projection_builder: Mock,
        ):
            with patch(
                "gilt.services.ingestion_orchestration_service.link_transfers",
                return_value=3,
            ):
                result = service.run_post_ingest(output_dir, mock_event_store, mock_es_service)

            assert isinstance(result, PostIngestResult)
            assert result.modified_transfer_count == 3
            assert result.events_processed == 5
            assert result.latest_event_sequence == 42

        def it_should_report_zero_auto_categorizations_when_no_rules_match(
            self,
            service: IngestionOrchestrationService,
            output_dir: Path,
            mock_event_store: Mock,
            mock_es_service: Mock,
        ):
            with (
                patch(
                    "gilt.services.ingestion_orchestration_service.link_transfers",
                    return_value=0,
                ),
                patch(
                    "gilt.services.ingestion_orchestration_service.RuleInferenceService"
                ) as MockRuleInference,
            ):
                mock_rule_svc = Mock()
                mock_rule_svc.infer_rules.return_value = []
                MockRuleInference.return_value = mock_rule_svc

                result = service.run_post_ingest(output_dir, mock_event_store, mock_es_service)

            assert result.auto_categorized_count == 0

        def it_should_count_auto_categorized_transactions_when_rules_match(
            self,
            service: IngestionOrchestrationService,
            output_dir: Path,
            mock_event_store: Mock,
            mock_es_service: Mock,
            mock_projection_builder: Mock,
        ):
            fake_transactions = [
                {"transaction_id": "abc1", "account_id": "MYBANK_CHQ", "canonical_description": "EXAMPLE UTILITY"},
                {"transaction_id": "abc2", "account_id": "MYBANK_CHQ", "canonical_description": "SAMPLE STORE"},
            ]
            mock_projection_builder.get_all_transactions.return_value = fake_transactions

            with (
                patch(
                    "gilt.services.ingestion_orchestration_service.link_transfers",
                    return_value=0,
                ),
                patch(
                    "gilt.services.ingestion_orchestration_service.RuleInferenceService"
                ) as MockRuleInference,
                patch(
                    "gilt.services.ingestion_orchestration_service.CategorizationPersistenceService"
                ) as MockPersistence,
                patch(
                    "gilt.services.ingestion_orchestration_service.categorization_updates_from_rule_matches",
                    return_value=["update1", "update2"],
                ),
            ):
                fake_rule = MagicMock()
                fake_matches = [MagicMock(), MagicMock()]

                mock_rule_svc = Mock()
                mock_rule_svc.infer_rules.return_value = [fake_rule]
                mock_rule_svc.run_rules.return_value = fake_matches
                MockRuleInference.return_value = mock_rule_svc

                mock_persist_svc = Mock()
                MockPersistence.return_value = mock_persist_svc

                result = service.run_post_ingest(output_dir, mock_event_store, mock_es_service)

            assert result.auto_categorized_count == 2
            mock_persist_svc.persist_categorizations.assert_called_once_with(["update1", "update2"])

        def it_should_report_total_transaction_count_from_projections(
            self,
            service: IngestionOrchestrationService,
            output_dir: Path,
            mock_event_store: Mock,
            mock_es_service: Mock,
            mock_projection_builder: Mock,
        ):
            mock_projection_builder.get_all_transactions.return_value = [
                {"transaction_id": "t1"},
                {"transaction_id": "t2"},
                {"transaction_id": "t3"},
            ]

            with patch(
                "gilt.services.ingestion_orchestration_service.link_transfers",
                return_value=0,
            ):
                result = service.run_post_ingest(output_dir, mock_event_store, mock_es_service)

            assert result.total_transactions == 3
