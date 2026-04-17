"""
Intelligence scan service - functional core for background transaction intelligence.

Extracts the pure business logic from IntelligenceWorker so it can be tested
without a QThread context.

NO IMPORTS FROM:
- PySide6/Qt
- rich
- typer

All dependencies are injected. All methods return data structures.
"""

from __future__ import annotations

from pathlib import Path

from gilt.model.category_io import format_category_path
from gilt.services.rule_inference_service import RuleInferenceService


class IntelligenceScanService:
    """
    Functional core for intelligence scanning operations.

    Each method returns a metadata fragment dict keyed by transaction_id.
    The caller (IntelligenceWorker) merges the fragments and checks for
    interruption between calls.

    Does NOT:
    - Emit Qt signals
    - Check isInterruptionRequested()
    - Display anything
    """

    def scan_duplicates(self, transactions, duplicate_service) -> dict[str, dict]:
        """Scan transactions for duplicate pairs.

        Args:
            transactions: List of Transaction model objects.
            duplicate_service: DuplicateService instance.

        Returns:
            Metadata fragment: {transaction_id: {"risk": True, "duplicate_match": match}}
        """
        metadata: dict[str, dict] = {}
        matches = duplicate_service.scan_transactions(transactions)
        for m in matches:
            for tid in [m.pair.txn1_id, m.pair.txn2_id]:
                if tid not in metadata:
                    metadata[tid] = {}
                metadata[tid]["risk"] = True
                metadata[tid]["duplicate_match"] = m
        return metadata

    def apply_inferred_rules(self, transactions, projections_path: Path) -> dict[str, dict]:
        """Apply inferred categorization rules to uncategorized transactions.

        Args:
            transactions: List of Transaction model objects.
            projections_path: Path to the projections database.

        Returns:
            Metadata fragment: {transaction_id: {"predicted_category": ..., "confidence": ...,
            "prediction_source": "rule"}}
        """
        metadata: dict[str, dict] = {}
        service = RuleInferenceService(projections_path)
        rules = service.infer_rules(min_evidence=3, min_confidence=0.9)
        if not rules:
            return metadata

        txn_dicts = [
            {
                "transaction_id": t.transaction_id,
                "canonical_description": t.description,
                "category": t.category,
                "account_id": t.account_id,
            }
            for t in transactions
        ]
        matches = service.apply_rules(txn_dicts, rules)
        for m in matches:
            tid = m.transaction["transaction_id"]
            if tid not in metadata:
                metadata[tid] = {}
            metadata[tid]["predicted_category"] = format_category_path(m.rule.category, m.rule.subcategory)
            metadata[tid]["confidence"] = m.rule.confidence
            metadata[tid]["prediction_source"] = "rule"
        return metadata

    def predict_categories(
        self,
        transactions,
        smart_category_service,
        skip_ids: set[str] | None = None,
    ) -> dict[str, dict]:
        """Predict categories for uncategorized transactions using the smart category service.

        Args:
            transactions: List of Transaction model objects.
            smart_category_service: SmartCategoryService instance.
            skip_ids: Transaction IDs to skip (e.g. already matched by rules).

        Returns:
            Metadata fragment: {transaction_id: {"predicted_category": ..., "confidence": ...}}
        """
        skip = skip_ids or set()
        metadata: dict[str, dict] = {}
        for txn in transactions:
            if not txn.category and txn.transaction_id not in skip:
                cat, conf = smart_category_service.predict_category(
                    txn.description, txn.amount, txn.account_id
                )
                if txn.transaction_id not in metadata:
                    metadata[txn.transaction_id] = {}
                metadata[txn.transaction_id]["confidence"] = conf
                metadata[txn.transaction_id]["predicted_category"] = cat
        return metadata


__all__ = ["IntelligenceScanService"]
