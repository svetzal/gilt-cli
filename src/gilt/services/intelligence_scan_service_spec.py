"""Tests for IntelligenceScanService."""

from __future__ import annotations

from datetime import date
from unittest.mock import Mock, patch

from gilt.model.duplicate import DuplicateAssessment, DuplicateMatch, TransactionPair
from gilt.services.intelligence_scan_service import IntelligenceScanService
from gilt.testing.fixtures import make_transaction


class DescribeScanDuplicates:
    def it_should_return_empty_dict_when_no_matches(self):
        svc = IntelligenceScanService()
        mock_dup = Mock()
        mock_dup.scan_transactions.return_value = []
        txns = [make_transaction(transaction_id="abc123")]
        result = svc.scan_duplicates(txns, mock_dup)
        assert result == {}

    def it_should_populate_metadata_for_both_transactions_in_a_match(self):
        svc = IntelligenceScanService()
        pair = TransactionPair(
            txn1_id="t1",
            txn1_date=date(2025, 1, 1),
            txn1_description="D1",
            txn1_amount=-10.0,
            txn1_account="acc",
            txn2_id="t2",
            txn2_date=date(2025, 1, 1),
            txn2_description="D2",
            txn2_amount=-10.0,
            txn2_account="acc",
        )
        match = DuplicateMatch(
            pair=pair,
            assessment=DuplicateAssessment(is_duplicate=True, confidence=0.9, reasoning=""),
        )
        mock_dup = Mock()
        mock_dup.scan_transactions.return_value = [match]
        txns = [make_transaction(transaction_id="t1"), make_transaction(transaction_id="t2")]

        result = svc.scan_duplicates(txns, mock_dup)

        assert "t1" in result
        assert result["t1"]["risk"] is True
        assert result["t1"]["duplicate_match"] is match
        assert "t2" in result
        assert result["t2"]["risk"] is True


class DescribeApplyInferredRules:
    def it_should_return_empty_dict_when_no_rules(self, tmp_path):
        svc = IntelligenceScanService()
        fake_projections = tmp_path / "projections.db"
        txns = [make_transaction(transaction_id="t1")]

        with patch("gilt.services.intelligence_scan_service.RuleInferenceService") as mock_rule_cls:
            mock_rule_svc = Mock()
            mock_rule_svc.infer_rules.return_value = []
            mock_rule_cls.return_value = mock_rule_svc

            result = svc.apply_inferred_rules(txns, fake_projections)

        assert result == {}

    def it_should_populate_metadata_for_rule_matched_transactions(self, tmp_path):
        svc = IntelligenceScanService()
        fake_projections = tmp_path / "projections.db"
        txns = [make_transaction(transaction_id="t1", description="EXAMPLE UTILITY")]

        mock_rule = Mock()
        mock_rule.category = "Utilities"
        mock_rule.subcategory = None
        mock_rule.confidence = 0.95

        mock_match = Mock()
        mock_match.transaction = {"transaction_id": "t1"}
        mock_match.rule = mock_rule

        with patch("gilt.services.intelligence_scan_service.RuleInferenceService") as mock_rule_cls:
            mock_rule_svc = Mock()
            mock_rule_svc.infer_rules.return_value = [mock_rule]
            mock_rule_svc.apply_rules.return_value = [mock_match]
            mock_rule_cls.return_value = mock_rule_svc

            result = svc.apply_inferred_rules(txns, fake_projections)

        assert "t1" in result
        assert result["t1"]["predicted_category"] == "Utilities"
        assert result["t1"]["prediction_source"] == "rule"
        assert result["t1"]["confidence"] == 0.95


class DescribePredictCategories:
    def it_should_skip_already_categorized_transactions(self):
        svc = IntelligenceScanService()
        txns = [make_transaction(transaction_id="t1", category="Food")]
        mock_smart = Mock()

        result = svc.predict_categories(txns, mock_smart)

        assert result == {}
        mock_smart.predict_category.assert_not_called()

    def it_should_skip_transactions_in_skip_ids(self):
        svc = IntelligenceScanService()
        txns = [make_transaction(transaction_id="t1")]
        mock_smart = Mock()

        result = svc.predict_categories(txns, mock_smart, skip_ids={"t1"})

        assert result == {}
        mock_smart.predict_category.assert_not_called()

    def it_should_predict_for_uncategorized_transactions(self):
        svc = IntelligenceScanService()
        txns = [make_transaction(transaction_id="t1")]
        mock_smart = Mock()
        mock_smart.predict_category.return_value = ("Food", 0.88)

        result = svc.predict_categories(txns, mock_smart)

        assert "t1" in result
        assert result["t1"]["predicted_category"] == "Food"
        assert result["t1"]["confidence"] == 0.88
