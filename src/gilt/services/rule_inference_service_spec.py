from unittest.mock import Mock, patch

from gilt.services.rule_inference_service import InferredRule, RuleInferenceService


def _txn(desc, category=None, subcategory=None, txn_id="t1", amount=-10.0):
    return {
        "transaction_id": txn_id,
        "canonical_description": desc,
        "category": category,
        "subcategory": subcategory,
        "amount": amount,
        "account_id": "MYBANK_CHQ",
        "transaction_date": "2025-01-15",
    }


class DescribeRuleInferenceService:
    def it_should_infer_rules_for_consistently_categorized_descriptions(self):
        txns = [
            _txn("EXAMPLE UTILITY", "Housing", "Utilities", txn_id="t1"),
            _txn("EXAMPLE UTILITY", "Housing", "Utilities", txn_id="t2"),
            _txn("EXAMPLE UTILITY", "Housing", "Utilities", txn_id="t3"),
        ]
        with patch("gilt.services.rule_inference_service.ProjectionBuilder") as MockPB:
            MockPB.return_value.get_all_transactions.return_value = txns
            service = RuleInferenceService(projections_db=Mock())

        rules = service.infer_rules(min_evidence=3, min_confidence=0.9)
        assert len(rules) == 1
        assert rules[0].description == "EXAMPLE UTILITY"
        assert rules[0].category == "Housing"
        assert rules[0].subcategory == "Utilities"
        assert rules[0].evidence_count == 3
        assert rules[0].confidence == 1.0

    def it_should_exclude_descriptions_below_min_evidence(self):
        txns = [
            _txn("RARE VENDOR", "Dining Out", None, txn_id="t1"),
            _txn("RARE VENDOR", "Dining Out", None, txn_id="t2"),
        ]
        with patch("gilt.services.rule_inference_service.ProjectionBuilder") as MockPB:
            MockPB.return_value.get_all_transactions.return_value = txns
            service = RuleInferenceService(projections_db=Mock())

        rules = service.infer_rules(min_evidence=3, min_confidence=0.9)
        assert len(rules) == 0

    def it_should_exclude_descriptions_below_min_confidence(self):
        txns = [
            _txn("MIXED VENDOR", "Groceries", None, txn_id="t1"),
            _txn("MIXED VENDOR", "Groceries", None, txn_id="t2"),
            _txn("MIXED VENDOR", "Dining Out", None, txn_id="t3"),
        ]
        with patch("gilt.services.rule_inference_service.ProjectionBuilder") as MockPB:
            MockPB.return_value.get_all_transactions.return_value = txns
            service = RuleInferenceService(projections_db=Mock())

        # 2/3 = 66.7% confidence, below 90%
        rules = service.infer_rules(min_evidence=3, min_confidence=0.9)
        assert len(rules) == 0

    def it_should_match_uncategorized_transactions_to_rules(self):
        rules = [
            InferredRule(
                description="EXAMPLE UTILITY",
                category="Housing",
                subcategory="Utilities",
                evidence_count=10,
                total_count=10,
                confidence=1.0,
            ),
        ]
        transactions = [
            _txn("EXAMPLE UTILITY", category=None, txn_id="new1"),
            _txn("UNKNOWN VENDOR", category=None, txn_id="new2"),
        ]

        with patch("gilt.services.rule_inference_service.ProjectionBuilder"):
            service = RuleInferenceService(projections_db=Mock())

        matches = service.apply_rules(transactions, rules)
        assert len(matches) == 1
        assert matches[0].transaction["transaction_id"] == "new1"
        assert matches[0].rule.category == "Housing"
        assert matches[0].rule.subcategory == "Utilities"

    def it_should_not_recategorize_already_categorized_transactions(self):
        rules = [
            InferredRule(
                description="EXAMPLE UTILITY",
                category="Housing",
                subcategory="Utilities",
                evidence_count=10,
                total_count=10,
                confidence=1.0,
            ),
        ]
        transactions = [
            _txn("EXAMPLE UTILITY", category="Entertainment", txn_id="already"),
        ]

        with patch("gilt.services.rule_inference_service.ProjectionBuilder"):
            service = RuleInferenceService(projections_db=Mock())

        matches = service.apply_rules(transactions, rules)
        assert len(matches) == 0

    def it_should_sort_rules_by_evidence_count_descending(self):
        txns = [
            *[_txn("HIGH EVIDENCE", "Groceries", None, txn_id=f"h{i}") for i in range(10)],
            *[_txn("LOW EVIDENCE", "Banking", "Fees", txn_id=f"l{i}") for i in range(3)],
        ]
        with patch("gilt.services.rule_inference_service.ProjectionBuilder") as MockPB:
            MockPB.return_value.get_all_transactions.return_value = txns
            service = RuleInferenceService(projections_db=Mock())

        rules = service.infer_rules(min_evidence=3, min_confidence=0.9)
        assert len(rules) == 2
        assert rules[0].description == "HIGH EVIDENCE"
        assert rules[1].description == "LOW EVIDENCE"

    def it_should_handle_subcategory_none_consistently(self):
        txns = [
            _txn("SAMPLE STORE", "Groceries", None, txn_id="t1"),
            _txn("SAMPLE STORE", "Groceries", None, txn_id="t2"),
            _txn("SAMPLE STORE", "Groceries", None, txn_id="t3"),
        ]
        with patch("gilt.services.rule_inference_service.ProjectionBuilder") as MockPB:
            MockPB.return_value.get_all_transactions.return_value = txns
            service = RuleInferenceService(projections_db=Mock())

        rules = service.infer_rules(min_evidence=3, min_confidence=0.9)
        assert len(rules) == 1
        assert rules[0].subcategory is None

    def it_should_ignore_uncategorized_transactions_when_inferring(self):
        txns = [
            _txn("EXAMPLE UTILITY", category=None, txn_id="t1"),
            _txn("EXAMPLE UTILITY", category=None, txn_id="t2"),
            _txn("EXAMPLE UTILITY", category=None, txn_id="t3"),
        ]
        with patch("gilt.services.rule_inference_service.ProjectionBuilder") as MockPB:
            MockPB.return_value.get_all_transactions.return_value = txns
            service = RuleInferenceService(projections_db=Mock())

        rules = service.infer_rules(min_evidence=3, min_confidence=0.9)
        assert len(rules) == 0
