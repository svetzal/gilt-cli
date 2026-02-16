from __future__ import annotations

"""
Adaptive prompt management for duplicate detection.

This module manages an evolving prompt that learns from user feedback about
duplicate detection decisions. The prompt is stored in the data directory
and improves over time based on confirmed/denied duplicates.

Privacy:
- All data stays local in the data directory.
- No external network calls.
"""

from pathlib import Path
import json
from datetime import datetime

from gilt.model.duplicate import TransactionPair


DEFAULT_PROMPT_TEMPLATE = """You are analyzing bank transactions to detect duplicates.

Banks sometimes modify transaction descriptions over time - they may add suffixes, remove details, or reformat text. Your job is to determine if two transactions are likely the same transaction recorded twice (a duplicate) or two separate legitimate transactions.

Consider:
- Date proximity (same day or very close = more likely duplicate)
- Amount exactness (same amount = strong duplicate signal)
- Description similarity (accounting for bank's text variations)
- Account matching (same account = more likely duplicate)

{learned_patterns}

Be conservative: when in doubt about whether transactions are duplicates, mark is_duplicate=false and explain your uncertainty in the reasoning.

Analyze these two transactions:

Transaction 1:
- Date: {{txn1_date}}
- Account: {{txn1_account}}
- Amount: {{txn1_amount}} CAD
- Description: {{txn1_description}}

Transaction 2:
- Date: {{txn2_date}}
- Account: {{txn2_account}}
- Amount: {{txn2_amount}} CAD
- Description: {{txn2_description}}

Assess whether these are duplicates."""


class PromptManager:
    """Manages an adaptive prompt that learns from user feedback."""

    def __init__(self, data_dir: Path):
        """Initialize prompt manager.

        Args:
            data_dir: Directory where prompt and feedback are stored
        """
        self.data_dir = data_dir
        self.prompt_file = data_dir / "duplicate_detection_prompt.json"
        self.feedback_history: list[dict] = []
        self._load_prompt()

    def _load_prompt(self) -> None:
        """Load prompt and feedback history from disk."""
        if self.prompt_file.exists():
            data = json.loads(self.prompt_file.read_text())
            self.feedback_history = data.get("feedback_history", [])
        else:
            self.feedback_history = []

    def _save_prompt(self) -> None:
        """Save prompt and feedback history to disk."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        data = {
            "version": 1,
            "last_updated": datetime.now().isoformat(),
            "feedback_history": self.feedback_history,
        }
        self.prompt_file.write_text(json.dumps(data, indent=2))

    def _generate_learned_patterns(self) -> str:
        """Generate learned patterns section from feedback history."""
        if not self.feedback_history:
            return ""

        # Count patterns
        confirmed_duplicates = [
            f for f in self.feedback_history if f["user_confirmed"] and f["llm_said_duplicate"]
        ]
        false_positives = [
            f for f in self.feedback_history if not f["user_confirmed"] and f["llm_said_duplicate"]
        ]
        false_negatives = [
            f for f in self.feedback_history if f["user_confirmed"] and not f["llm_said_duplicate"]
        ]

        patterns = ["LEARNED PATTERNS FROM PAST DECISIONS:"]
        patterns.append("")

        # Add insights about false positives
        if false_positives:
            patterns.append("Common FALSE POSITIVES to avoid:")

            # Look for location pattern — extract distinct location tokens
            # and flag when descriptions differ only by location
            location_patterns = []
            for fp in false_positives[-5:]:  # Last 5 false positives
                desc1 = fp.get("txn1_description", "")
                desc2 = fp.get("txn2_description", "")
                tokens1 = set(desc1.split())
                tokens2 = set(desc2.split())
                diff = tokens1.symmetric_difference(tokens2)
                if diff and tokens1 - tokens2 and tokens2 - tokens1:
                    location_patterns.append(
                        "- Transactions with same amount/date but different location "
                        "tokens are typically separate events, NOT duplicates"
                    )
                    break

            patterns.extend(location_patterns)

            # Add general guidance if we found patterns
            if location_patterns:
                patterns.append(
                    "- Even with same amount and date, different locations usually mean different transactions"
                )
            patterns.append("")

        # Add insights about confirmed duplicates
        if confirmed_duplicates:
            patterns.append("Common TRUE DUPLICATES to recognize:")
            recent_confirmed = confirmed_duplicates[-3:]  # Last 3 confirmed
            for cd in recent_confirmed:
                desc1 = cd.get("txn1_description", "")
                desc2 = cd.get("txn2_description", "")
                if desc1 and desc2:
                    patterns.append(f"- '{desc1}' and '{desc2}' were confirmed as duplicates")
            patterns.append("")

        if false_negatives:
            patterns.append("Don't miss these patterns (previously missed duplicates):")
            for fn in false_negatives[-3:]:
                desc1 = fn.get("txn1_description", "")
                desc2 = fn.get("txn2_description", "")
                if desc1 and desc2:
                    patterns.append(f"- '{desc1}' and '{desc2}' ARE duplicates despite differences")
            patterns.append("")

        return "\n".join(patterns)

    def get_prompt(self) -> str:
        """Get the current prompt with learned patterns.

        Returns:
            Prompt template with {{variable}} placeholders
        """
        learned_patterns = self._generate_learned_patterns()
        return DEFAULT_PROMPT_TEMPLATE.format(learned_patterns=learned_patterns)

    def add_feedback(
        self,
        pair: TransactionPair,
        llm_said_duplicate: bool,
        llm_confidence: float,
        user_confirmed: bool,
        llm_reasoning: str = "",
    ) -> None:
        """Add user feedback about a duplicate detection decision.

        Args:
            pair: The transaction pair that was assessed
            llm_said_duplicate: What the LLM predicted
            llm_confidence: LLM's confidence level
            user_confirmed: Whether the user confirmed it as a duplicate
            llm_reasoning: The LLM's reasoning for its decision
        """
        feedback = {
            "timestamp": datetime.now().isoformat(),
            "txn1_date": str(pair.txn1_date),
            "txn1_description": pair.txn1_description,
            "txn1_amount": pair.txn1_amount,
            "txn2_date": str(pair.txn2_date),
            "txn2_description": pair.txn2_description,
            "txn2_amount": pair.txn2_amount,
            "llm_said_duplicate": llm_said_duplicate,
            "llm_confidence": llm_confidence,
            "user_confirmed": user_confirmed,
            "llm_reasoning": llm_reasoning,
        }
        self.feedback_history.append(feedback)
        self._save_prompt()

    def get_stats(self) -> dict:
        """Get statistics about the feedback history.

        Returns:
            Dictionary with accuracy metrics
        """
        if not self.feedback_history:
            return {
                "total_feedback": 0,
                "accuracy": 0.0,
                "true_positives": 0,
                "false_positives": 0,
                "true_negatives": 0,
                "false_negatives": 0,
            }

        tp = sum(
            1 for f in self.feedback_history if f["llm_said_duplicate"] and f["user_confirmed"]
        )
        fp = sum(
            1 for f in self.feedback_history if f["llm_said_duplicate"] and not f["user_confirmed"]
        )
        tn = sum(
            1
            for f in self.feedback_history
            if not f["llm_said_duplicate"] and not f["user_confirmed"]
        )
        fn = sum(
            1 for f in self.feedback_history if not f["llm_said_duplicate"] and f["user_confirmed"]
        )

        total = len(self.feedback_history)
        correct = tp + tn
        accuracy = correct / total if total > 0 else 0.0

        return {
            "total_feedback": total,
            "accuracy": accuracy,
            "true_positives": tp,
            "false_positives": fp,
            "true_negatives": tn,
            "false_negatives": fn,
        }


__all__ = ["PromptManager"]
