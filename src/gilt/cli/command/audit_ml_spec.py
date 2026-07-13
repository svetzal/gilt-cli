from __future__ import annotations

"""
Tests for audit-ml CLI command.

Mocks at service/builder boundaries, not at library internals.
"""

from unittest.mock import MagicMock, patch

import pytest

from gilt.cli.command._errors import CommandAbort
from gilt.cli.command.audit_ml import run
from gilt.services.event_sourcing_service import EventSourcingReadyResult


class DescribeAuditMlCommand:
    def it_should_return_error_when_event_store_not_found(self, tmp_path):
        workspace = MagicMock()
        workspace.event_store_path = tmp_path / "nonexistent" / "events.db"

        with pytest.raises(CommandAbort) as exc_info:
            run(workspace=workspace, mode="summary")

        assert exc_info.value.code == 1

    def it_should_return_error_for_unknown_mode(self, tmp_path):
        event_store_path = tmp_path / "events.db"
        event_store_path.touch()

        workspace = MagicMock()
        workspace.event_store_path = event_store_path

        with patch("gilt.cli.event_sourcing_bootstrap.EventSourcingService") as mock_es_cls:
            mock_es = MagicMock()
            mock_es.ensure_ready.return_value = EventSourcingReadyResult(
                ready=True,
                event_store=MagicMock(),
                projection_builder=MagicMock(),
            )
            mock_es_cls.return_value = mock_es

            result = run(workspace=workspace, mode="banana")

        assert result == 1

    def it_should_show_summary_with_no_training_data(self, tmp_path):
        event_store_path = tmp_path / "events.db"
        event_store_path.touch()

        workspace = MagicMock()
        workspace.event_store_path = event_store_path

        with (
            patch("gilt.cli.event_sourcing_bootstrap.EventSourcingService") as mock_es_cls,
            patch("gilt.cli.command.audit_ml.TrainingDataBuilder") as mock_builder_cls,
        ):
            mock_es = MagicMock()
            mock_es.ensure_ready.return_value = EventSourcingReadyResult(
                ready=True,
                event_store=MagicMock(),
                projection_builder=MagicMock(),
            )
            mock_es_cls.return_value = mock_es

            mock_builder = MagicMock()
            mock_builder.get_statistics.return_value = {
                "total_examples": 0,
                "positive_examples": 0,
                "negative_examples": 0,
                "class_balance": 0.0,
                "sufficient_for_training": False,
            }
            mock_builder_cls.return_value = mock_builder

            result = run(workspace=workspace, mode="summary")

        assert result == 0
        mock_builder.get_statistics.assert_called_once()

    def it_should_show_training_data_when_available(self, tmp_path):
        event_store_path = tmp_path / "events.db"
        event_store_path.touch()

        workspace = MagicMock()
        workspace.event_store_path = event_store_path

        with (
            patch("gilt.cli.event_sourcing_bootstrap.EventSourcingService") as mock_es_cls,
            patch("gilt.cli.command.audit_ml.TrainingDataBuilder") as mock_builder_cls,
        ):
            mock_es = MagicMock()
            mock_es.ensure_ready.return_value = EventSourcingReadyResult(
                ready=True,
                event_store=MagicMock(),
                projection_builder=MagicMock(),
            )
            mock_es_cls.return_value = mock_es

            mock_builder = MagicMock()
            mock_builder.load_from_events.return_value = ([], [])
            mock_builder_cls.return_value = mock_builder

            result = run(workspace=workspace, mode="training")

        assert result == 0
        mock_builder.load_from_events.assert_called_once()
