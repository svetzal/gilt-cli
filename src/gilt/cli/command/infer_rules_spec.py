from pathlib import Path
from unittest.mock import Mock, patch

from gilt.cli.command import infer_rules
from gilt.services.event_sourcing_service import EventSourcingReadyResult


def _make_workspace(tmp_path):
    ws = Mock()
    ws.projections_path = tmp_path / "projections.db"
    ws.categories_config = tmp_path / "categories.yml"
    ws.ledger_data_dir = tmp_path / "accounts"
    ws.event_store_path = tmp_path / "events.db"
    return ws


class DescribeInferRulesCommand:
    def it_should_return_error_when_projections_missing(self, tmp_path):
        ws = _make_workspace(tmp_path)
        code = infer_rules.run(workspace=ws)
        assert code == 1

    def it_should_display_rules_in_preview_mode(self, tmp_path):
        ws = _make_workspace(tmp_path)
        ws.projections_path.touch()

        mock_rule = Mock()
        mock_rule.description = "EXAMPLE UTILITY"
        mock_rule.category = "Housing"
        mock_rule.subcategory = "Utilities"
        mock_rule.evidence_count = 10
        mock_rule.total_count = 10
        mock_rule.confidence = 1.0

        with patch("gilt.cli.command.infer_rules.RuleInferenceService") as MockSvc:
            MockSvc.return_value.infer_rules.return_value = [mock_rule]
            code = infer_rules.run(workspace=ws)

        assert code == 0
        MockSvc.return_value.infer_rules.assert_called_once()

    def it_should_show_no_rules_message_when_none_inferred(self, tmp_path):
        ws = _make_workspace(tmp_path)
        ws.projections_path.touch()

        with patch("gilt.cli.command.infer_rules.RuleInferenceService") as MockSvc:
            MockSvc.return_value.infer_rules.return_value = []
            code = infer_rules.run(workspace=ws)

        assert code == 0

    def it_should_dry_run_apply_without_writing(self, tmp_path):
        ws = _make_workspace(tmp_path)
        ws.projections_path.touch()

        mock_rule = Mock()
        mock_rule.description = "EXAMPLE UTILITY"
        mock_rule.category = "Housing"
        mock_rule.subcategory = "Utilities"
        mock_rule.evidence_count = 10
        mock_rule.total_count = 10
        mock_rule.confidence = 1.0

        mock_match = Mock()
        mock_match.transaction = {
            "transaction_id": "abc12345",
            "transaction_date": "2025-01-15",
            "account_id": "MYBANK_CHQ",
            "canonical_description": "EXAMPLE UTILITY",
            "amount": -50.0,
        }
        mock_match.rule = mock_rule

        with (
            patch("gilt.cli.command.infer_rules.RuleInferenceService") as MockSvc,
            patch("gilt.cli.command.infer_rules.ProjectionBuilder") as MockPB,
        ):
            MockSvc.return_value.infer_rules.return_value = [mock_rule]
            MockSvc.return_value.apply_rules.return_value = [mock_match]
            MockPB.return_value.get_all_transactions.return_value = []

            code = infer_rules.run(workspace=ws, apply=True, write=False)

        assert code == 0

    def it_should_write_events_when_apply_and_write(self, tmp_path):
        ws = _make_workspace(tmp_path)
        ws.projections_path.touch()
        ws.ledger_data_dir.mkdir(parents=True)

        mock_rule = Mock()
        mock_rule.description = "EXAMPLE UTILITY"
        mock_rule.category = "Housing"
        mock_rule.subcategory = "Utilities"
        mock_rule.evidence_count = 10
        mock_rule.total_count = 10
        mock_rule.confidence = 1.0

        mock_match = Mock()
        mock_match.transaction = {
            "transaction_id": "abc12345",
            "transaction_date": "2025-01-15",
            "account_id": "MYBANK_CHQ",
            "canonical_description": "EXAMPLE UTILITY",
            "amount": -50.0,
        }
        mock_match.rule = mock_rule

        mock_event_store = Mock()
        mock_projection_builder = Mock()

        with (
            patch("gilt.cli.command.infer_rules.RuleInferenceService") as MockSvc,
            patch("gilt.cli.command.infer_rules.ProjectionBuilder") as MockPB,
            patch("gilt.cli.command.util.EventSourcingService") as MockES,
        ):
            MockSvc.return_value.infer_rules.return_value = [mock_rule]
            MockSvc.return_value.apply_rules.return_value = [mock_match]
            MockPB.return_value.get_all_transactions.return_value = []
            MockES.return_value.ensure_ready.return_value = EventSourcingReadyResult(
                ready=True,
                event_store=mock_event_store,
                projection_builder=mock_projection_builder,
            )

            code = infer_rules.run(workspace=ws, apply=True, write=True)

        assert code == 0
        # Event was emitted with source='rule'
        mock_event_store.append_event.assert_called_once()
        event = mock_event_store.append_event.call_args[0][0]
        assert event.source == "rule"
        assert event.category == "Housing"
        assert event.subcategory == "Utilities"
        assert event.transaction_id == "abc12345"

    def it_should_export_rules_to_json(self, tmp_path):
        ws = _make_workspace(tmp_path)
        ws.projections_path.touch()

        mock_rule = Mock()
        mock_rule.description = "EXAMPLE UTILITY"
        mock_rule.category = "Housing"
        mock_rule.subcategory = "Utilities"
        mock_rule.evidence_count = 10
        mock_rule.total_count = 10
        mock_rule.confidence = 1.0

        export_path = str(tmp_path / "rules.json")

        with patch("gilt.cli.command.infer_rules.RuleInferenceService") as MockSvc:
            MockSvc.return_value.infer_rules.return_value = [mock_rule]
            code = infer_rules.run(workspace=ws, export=export_path)

        assert code == 0
        import json

        data = json.loads(Path(export_path).read_text())
        assert len(data) == 1
        assert data[0]["description"] == "EXAMPLE UTILITY"
