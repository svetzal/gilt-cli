from __future__ import annotations

"""
Tests for prompt-stats CLI command.

Mocks at service/event-store boundaries, not at library internals.
"""

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from gilt.cli.command.prompt_stats import run
from gilt.services.event_sourcing_service import EventSourcingReadyResult


def _make_status(exists: bool) -> MagicMock:
    status = MagicMock()
    status.exists = exists
    return status


def _make_accuracy_metrics(total_feedback: int = 0) -> MagicMock:
    metrics = MagicMock()
    metrics.total_feedback = total_feedback
    metrics.accuracy = 0.85
    metrics.precision = 0.80
    metrics.recall = 0.90
    metrics.f1_score = 0.85
    metrics.true_positives = 8
    metrics.false_positives = 2
    metrics.true_negatives = 9
    metrics.false_negatives = 1
    return metrics


class DescribePromptStatsCommand:
    def it_should_return_error_when_data_dir_not_found(self):
        workspace = MagicMock()
        workspace.ledger_data_dir = Path("/nonexistent/path/accounts")
        workspace.event_store_path = Path("/nonexistent/path/events.db")

        result = run(workspace=workspace)

        assert result == 1

    def it_should_return_error_when_event_store_not_found(self):
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            data_dir = tmp / "accounts"
            data_dir.mkdir()

            workspace = MagicMock()
            workspace.ledger_data_dir = data_dir
            workspace.event_store_path = tmp / "events.db"

            with patch("gilt.cli.command.util.EventSourcingService") as mock_es_cls:
                mock_es = MagicMock()
                mock_es.ensure_ready.return_value = EventSourcingReadyResult(
                    ready=False,
                    error="no_data",
                )
                mock_es_cls.return_value = mock_es

                result = run(workspace=workspace)

            assert result == 1

    def it_should_show_no_feedback_message_when_no_feedback(self):
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            data_dir = tmp / "accounts"
            data_dir.mkdir()

            workspace = MagicMock()
            workspace.ledger_data_dir = data_dir
            workspace.event_store_path = tmp / "events.db"

            with (
                patch("gilt.cli.command.util.EventSourcingService") as mock_es_cls,
                patch("gilt.cli.command.prompt_stats.PromptLearningService") as mock_learning_cls,
            ):
                mock_event_store = MagicMock()
                mock_event_store.get_events_by_type.return_value = []
                mock_es = MagicMock()
                mock_es.ensure_ready.return_value = EventSourcingReadyResult(
                    ready=True,
                    event_store=mock_event_store,
                    projection_builder=MagicMock(),
                )
                mock_es_cls.return_value = mock_es

                mock_learning = MagicMock()
                mock_learning.calculate_accuracy.return_value = _make_accuracy_metrics(
                    total_feedback=0
                )
                mock_learning_cls.return_value = mock_learning

                result = run(workspace=workspace)

            assert result == 0
            mock_learning.calculate_accuracy.assert_called_once()

    def it_should_display_accuracy_metrics_when_feedback_exists(self):
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            data_dir = tmp / "accounts"
            data_dir.mkdir()

            workspace = MagicMock()
            workspace.ledger_data_dir = data_dir
            workspace.event_store_path = tmp / "events.db"

            with (
                patch("gilt.cli.command.util.EventSourcingService") as mock_es_cls,
                patch("gilt.cli.command.prompt_stats.PromptLearningService") as mock_learning_cls,
            ):
                mock_event_store = MagicMock()
                mock_event_store.get_events_by_type.return_value = []
                mock_es = MagicMock()
                mock_es.ensure_ready.return_value = EventSourcingReadyResult(
                    ready=True,
                    event_store=mock_event_store,
                    projection_builder=MagicMock(),
                )
                mock_es_cls.return_value = mock_es

                mock_learning = MagicMock()
                mock_learning.calculate_accuracy.return_value = _make_accuracy_metrics(
                    total_feedback=10
                )
                mock_learning.identify_learned_patterns.return_value = []
                mock_learning_cls.return_value = mock_learning

                result = run(workspace=workspace)

            assert result == 0
            mock_learning.calculate_accuracy.assert_called_once()
            mock_learning.identify_learned_patterns.assert_called_once()

    def it_should_display_prompt_history(self):
        with TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            data_dir = tmp / "accounts"
            data_dir.mkdir()

            workspace = MagicMock()
            workspace.ledger_data_dir = data_dir
            workspace.event_store_path = tmp / "events.db"

            with (
                patch("gilt.cli.command.util.EventSourcingService") as mock_es_cls,
                patch("gilt.cli.command.prompt_stats.PromptLearningService") as mock_learning_cls,
            ):
                from datetime import datetime

                from gilt.model.events import PromptUpdated

                prompt_event = MagicMock(spec=PromptUpdated)
                prompt_event.prompt_version = "v2"
                prompt_event.accuracy_metrics = {"accuracy": 0.85}
                prompt_event.learned_patterns = ["pattern_a", "pattern_b"]
                prompt_event.event_timestamp = datetime(2025, 10, 1, 12, 0)

                mock_event_store = MagicMock()
                mock_event_store.get_events_by_type.return_value = [prompt_event]
                mock_es = MagicMock()
                mock_es.ensure_ready.return_value = EventSourcingReadyResult(
                    ready=True,
                    event_store=mock_event_store,
                    projection_builder=MagicMock(),
                )
                mock_es_cls.return_value = mock_es

                mock_learning = MagicMock()
                mock_learning.calculate_accuracy.return_value = _make_accuracy_metrics(
                    total_feedback=5
                )
                mock_learning.identify_learned_patterns.return_value = []
                mock_learning_cls.return_value = mock_learning

                result = run(workspace=workspace)

            assert result == 0
