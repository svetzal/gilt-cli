from __future__ import annotations

"""
Duplicate transaction detection service using LLM-based comparison.

This service scans ledger files for potential duplicate transactions, using
an LLM with structured output to assess whether transactions are duplicates
despite variations in description text.

Privacy:
- Uses local LLM inference via mojentic (no external API calls).
- Operates entirely on local ledger files.
"""

from datetime import timedelta
from pathlib import Path
from typing import List, Optional

from mojentic.llm.gateways.models import LLMMessage
from mojentic.llm.llm_broker import LLMBroker

from finance.model.account import Transaction, TransactionGroup
from finance.model.duplicate import (
    DuplicateAssessment,
    DuplicateMatch,
    TransactionPair,
)
from finance.model.ledger_io import load_ledger_csv
from finance.transfer.prompt_manager import PromptManager


class DuplicateDetector:
    """Service for detecting duplicate transactions using LLM analysis."""

    def __init__(self, model: str = "qwen2.5:3b", data_dir: Optional[Path] = None):
        """Initialize detector with specified model.

        Args:
            model: Ollama model name to use for analysis
            data_dir: Directory for storing adaptive prompt (optional)
        """
        self.model = model
        self._llm: Optional[LLMBroker] = None
        self.prompt_manager: Optional[PromptManager] = None
        if data_dir:
            self.prompt_manager = PromptManager(data_dir)

    def _get_llm(self) -> LLMBroker:
        """Lazy-initialize LLM broker."""
        if self._llm is None:
            self._llm = LLMBroker(model=self.model)
        return self._llm

    def load_all_transactions(self, data_dir: Path) -> List[Transaction]:
        """Load all transactions from all ledger files.

        Args:
            data_dir: Directory containing ledger CSV files

        Returns:
            List of all transactions sorted by date
        """
        transactions: List[Transaction] = []

        if not data_dir.exists():
            return transactions

        for ledger_file in data_dir.glob("*.csv"):
            text = ledger_file.read_text()
            groups = load_ledger_csv(text)
            for group in groups:
                transactions.append(group.primary)

        # Sort by date for efficient comparison
        transactions.sort(key=lambda t: (t.date, t.account_id, t.transaction_id))
        return transactions

    def find_potential_duplicates(
        self,
        transactions: List[Transaction],
        max_days_apart: int = 1,
        amount_tolerance: float = 0.001,
    ) -> List[TransactionPair]:
        """Find candidate transaction pairs that might be duplicates.

        Uses strict heuristics to narrow down pairs before LLM analysis:
        - Exact same amount (within tiny tolerance for floating point)
        - Same day or within max_days_apart (default 1 day)
        - Same account
        - Different descriptions (no point checking identical ones)

        This focuses on the bank description variation problem where the same
        transaction appears with modified text but same core details.

        Args:
            transactions: List of all transactions to analyze
            max_days_apart: Maximum days between potential duplicates (default 1)
            amount_tolerance: Acceptable difference in amounts (default 0.001)

        Returns:
            List of transaction pairs to analyze with LLM
        """
        pairs: List[TransactionPair] = []

        # Compare each transaction with subsequent ones
        for i, txn1 in enumerate(transactions):
            # Only look ahead at transactions within the date window
            for txn2 in transactions[i + 1 :]:
                # Stop if we're beyond the date window
                date_diff = abs((txn2.date - txn1.date).days)
                if date_diff > max_days_apart:
                    break

                # Check same account
                if txn1.account_id != txn2.account_id:
                    continue

                # Check amount is exactly the same (within rounding tolerance)
                amount_diff = abs(txn1.amount - txn2.amount)
                if amount_diff > amount_tolerance:
                    continue

                # Skip if descriptions are identical (not duplicates, just repeated)
                if txn1.description == txn2.description:
                    continue

                # This is a candidate pair
                pairs.append(
                    TransactionPair(
                        txn1_id=txn1.transaction_id,
                        txn1_date=txn1.date,
                        txn1_description=txn1.description,
                        txn1_amount=txn1.amount,
                        txn1_account=txn1.account_id,
                        txn2_id=txn2.transaction_id,
                        txn2_date=txn2.date,
                        txn2_description=txn2.description,
                        txn2_amount=txn2.amount,
                        txn2_account=txn2.account_id,
                    )
                )

        return pairs

    def assess_duplicate(self, pair: TransactionPair) -> DuplicateAssessment:
        """Use LLM to assess if a transaction pair is a duplicate.

        Args:
            pair: Transaction pair to analyze

        Returns:
            Assessment with is_duplicate, confidence, and reasoning
        """
        llm = self._get_llm()

        # Get the prompt template (with learned patterns if available)
        if self.prompt_manager:
            prompt_template = self.prompt_manager.get_prompt()
        else:
            # Fallback to a basic prompt
            prompt_template = """You are analyzing bank transactions to detect duplicates.

Banks sometimes modify transaction descriptions over time - they may add suffixes, remove details, or reformat text. Your job is to determine if two transactions are likely the same transaction recorded twice (a duplicate) or two separate legitimate transactions.

Consider:
- Date proximity (same day or very close = more likely duplicate)
- Amount exactness (same amount = strong duplicate signal)
- Description similarity (accounting for bank's text variations)
- Account matching (same account = more likely duplicate)

Be conservative: when in doubt about whether transactions are duplicates, mark is_duplicate=false and explain your uncertainty in the reasoning.

Analyze these two transactions:

Transaction 1:
- Date: {txn1_date}
- Account: {txn1_account}
- Amount: {txn1_amount} CAD
- Description: {txn1_description}

Transaction 2:
- Date: {txn2_date}
- Account: {txn2_account}
- Amount: {txn2_amount} CAD
- Description: {txn2_description}

Assess whether these are duplicates."""

        prompt = prompt_template.format(
            txn1_date=pair.txn1_date,
            txn1_account=pair.txn1_account,
            txn1_amount=pair.txn1_amount,
            txn1_description=pair.txn1_description,
            txn2_date=pair.txn2_date,
            txn2_account=pair.txn2_account,
            txn2_amount=pair.txn2_amount,
            txn2_description=pair.txn2_description,
        )

        result = llm.generate_object(
            messages=[LLMMessage(content=prompt)],
            object_model=DuplicateAssessment,
        )
        # Type assertion since we know generate_object returns the model type
        assert isinstance(result, DuplicateAssessment)
        return result

    def scan_for_duplicates(
        self,
        data_dir: Path,
        max_days_apart: int = 1,
        amount_tolerance: float = 0.001,
    ) -> List[DuplicateMatch]:
        """Scan all ledgers for duplicate transactions.

        Args:
            data_dir: Directory containing ledger CSV files
            max_days_apart: Maximum days between potential duplicates (default 1)
            amount_tolerance: Acceptable difference in amounts (default 0.001)

        Returns:
            List of detected duplicate matches with confidence scores
        """
        transactions = self.load_all_transactions(data_dir)
        candidate_pairs = self.find_potential_duplicates(
            transactions, max_days_apart, amount_tolerance
        )

        matches: List[DuplicateMatch] = []
        for pair in candidate_pairs:
            assessment = self.assess_duplicate(pair)
            match = DuplicateMatch(pair=pair, assessment=assessment)
            matches.append(match)

        # Sort by confidence (highest first) for better user experience
        matches.sort(key=lambda m: m.assessment.confidence, reverse=True)
        return matches


__all__ = ["DuplicateDetector"]
