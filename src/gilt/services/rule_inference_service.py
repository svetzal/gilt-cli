"""
Rule inference service - extract categorization rules from user history.

Analyzes categorization history to find descriptions that have been consistently
categorized the same way (e.g., >=3 times with >=90% agreement). These patterns
become deterministic rules that can auto-categorize new transactions without ML.

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. All functions return data structures.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from gilt.storage.projection import ProjectionBuilder


@dataclass
class InferredRule:
    """A categorization rule inferred from user history."""

    description: str
    category: str
    subcategory: str | None
    evidence_count: int
    total_count: int
    confidence: float


@dataclass
class RuleMatch:
    """A transaction matched against an inferred rule."""

    transaction: dict
    rule: InferredRule


class RuleInferenceService:
    """Infers categorization rules from transaction history.

    Scans the projections database for descriptions that have been categorized
    consistently. When the same description maps to the same category at least
    `min_evidence` times with at least `min_confidence` agreement, it becomes
    a rule.
    """

    def __init__(self, projections_db: Path):
        self._projection_builder = ProjectionBuilder(projections_db)

    def infer_rules(
        self,
        min_evidence: int = 3,
        min_confidence: float = 0.9,
    ) -> list[InferredRule]:
        """Extract consistent categorization patterns from history.

        Groups all categorized transactions by canonical_description, counts
        category usage per description, and returns rules where one category
        accounts for >= min_confidence of uses.

        Args:
            min_evidence: Minimum number of categorizations to consider a rule
            min_confidence: Minimum fraction of categorizations that must agree

        Returns:
            List of InferredRule sorted by evidence_count descending
        """
        all_txns = self._projection_builder.get_all_transactions(include_duplicates=False)

        # Group categorized transactions by description
        desc_categories: dict[str, list[tuple[str, str | None]]] = {}
        for txn in all_txns:
            cat = txn.get("category")
            desc = txn.get("canonical_description")
            if cat and desc:
                desc_categories.setdefault(desc, []).append((cat, txn.get("subcategory")))

        rules: list[InferredRule] = []
        for desc, cat_list in desc_categories.items():
            total = len(cat_list)
            if total < min_evidence:
                continue

            # Count each (category, subcategory) pair
            counts: dict[tuple[str, str | None], int] = {}
            for pair in cat_list:
                counts[pair] = counts.get(pair, 0) + 1

            # Find the dominant category
            best_pair, best_count = max(counts.items(), key=lambda x: x[1])
            confidence = best_count / total

            if confidence >= min_confidence:
                rules.append(
                    InferredRule(
                        description=desc,
                        category=best_pair[0],
                        subcategory=best_pair[1],
                        evidence_count=best_count,
                        total_count=total,
                        confidence=confidence,
                    )
                )

        rules.sort(key=lambda r: r.evidence_count, reverse=True)
        return rules

    def apply_rules(
        self,
        transactions: list[dict],
        rules: list[InferredRule],
    ) -> list[RuleMatch]:
        """Match uncategorized transactions against inferred rules.

        Only matches transactions that have no category assigned. Matches
        by exact canonical_description.

        Args:
            transactions: Transaction dicts (from projections)
            rules: Inferred rules to match against

        Returns:
            List of RuleMatch for transactions that matched a rule
        """
        rule_lookup = {r.description: r for r in rules}

        matches: list[RuleMatch] = []
        for txn in transactions:
            if txn.get("category"):
                continue
            desc = txn.get("canonical_description")
            if desc and desc in rule_lookup:
                matches.append(RuleMatch(transaction=txn, rule=rule_lookup[desc]))

        return matches


__all__ = ["InferredRule", "RuleMatch", "RuleInferenceService"]
