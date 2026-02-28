from __future__ import annotations

"""
Duplicate transaction detection service with ML and LLM-based comparison.

This service scans ledger files for potential duplicate transactions, using
either fast ML-based classification (default) or LLM analysis (fallback).

Privacy:
- ML uses local scikit-learn/LightGBM (no external API calls).
- LLM uses local inference via mojentic (no external API calls).
- All processing happens on local ledger files only.
"""

from pathlib import Path

from mojentic.llm.gateways.models import LLMMessage
from mojentic.llm.llm_broker import LLMBroker

from gilt.config import DEFAULT_OLLAMA_MODEL
from gilt.model.account import Transaction
from gilt.model.duplicate import (
    DuplicateAssessment,
    DuplicateMatch,
    TransactionPair,
)
from gilt.model.events import PromptUpdated
from gilt.storage.event_store import EventStore
from gilt.transfer.prompt_manager import PromptManager


class DuplicateDetector:
    """Service for detecting duplicate transactions using ML or LLM analysis."""

    def __init__(
        self,
        model: str = DEFAULT_OLLAMA_MODEL,
        data_dir: Path | None = None,
        event_store_path: Path | None = None,
        use_ml: bool = True,
        projections_path: Path | None = None,
    ):
        """Initialize detector with specified model and learned patterns.

        Args:
            model: Ollama model name to use for LLM analysis
            data_dir: Directory for storing adaptive prompt (optional, deprecated)
            event_store_path: Path to event store for loading learned patterns
            use_ml: Use ML classifier (True) or LLM (False). Default True.
            projections_path: Path to projections database (optional)
        """
        self.model = model
        self.use_ml = use_ml
        self.projections_path = projections_path
        self._llm: LLMBroker | None = None
        self._ml_classifier = None
        self.prompt_manager: PromptManager | None = None
        if data_dir:
            self.prompt_manager = PromptManager(data_dir)

        # Load latest PromptUpdated event for learned patterns
        self.prompt_version = "v1"
        self.learned_patterns: list[str] = []
        if event_store_path and event_store_path.exists():
            self._load_learned_patterns(event_store_path)
            # Initialize ML classifier from training data if use_ml is True
            if use_ml:
                self._ml_classifier = self._init_ml_classifier(event_store_path)

    def _init_ml_classifier(self, event_store_path: Path):
        """Initialize and train ML classifier from event store.

        Returns:
            Trained classifier or None if insufficient training data
        """
        try:
            from gilt.ml.duplicate_classifier import DuplicateClassifier
            from gilt.ml.training_data_builder import TrainingDataBuilder

            # Extract training data from confirmed/rejected duplicates
            event_store = EventStore(str(event_store_path))
            builder = TrainingDataBuilder(event_store)
            pairs, labels = builder.load_from_events()

            if len(pairs) < 10:
                # Not enough training data, will fall back to LLM
                return None

            # Train classifier
            classifier = DuplicateClassifier()
            classifier.train(pairs, labels)

            return classifier

        except ImportError:
            # ML dependencies not installed, fall back to LLM
            return None
        except Exception:
            # Training failed, fall back to LLM
            return None

    def _load_learned_patterns(self, event_store_path: Path) -> None:
        """Load latest PromptUpdated event to get learned patterns.

        Args:
            event_store_path: Path to the event store database
        """
        try:
            event_store = EventStore(str(event_store_path))
            prompt_events = event_store.get_events_by_type("PromptUpdated")

            if prompt_events:
                # Get most recent PromptUpdated event
                latest_event = prompt_events[-1]
                if isinstance(latest_event, PromptUpdated):
                    self.prompt_version = latest_event.prompt_version
                    self.learned_patterns = latest_event.learned_patterns
        except Exception:
            # If loading fails, just use defaults (v1 with no patterns)
            pass

    def _get_llm(self) -> LLMBroker:
        """Lazy-initialize LLM broker."""
        if self._llm is None:
            self._llm = LLMBroker(model=self.model)
        return self._llm

    def load_all_transactions(self, data_dir: Path) -> list[Transaction]:
        """Load all transactions from projections database.

        Args:
            data_dir: Directory containing ledger CSVs (for backward compatibility,
                     but projections are always at data/projections.db)

        Returns:
            List of all transactions sorted by date
        """
        from gilt.storage.projection import ProjectionBuilder

        transactions: list[Transaction] = []

        # Use provided projections_path or fall back to default
        projections_path = self.projections_path or Path("data/projections.db")
        if not projections_path.exists():
            return transactions

        # Load from projections (excludes confirmed duplicates)
        # This ensures that once a duplicate is confirmed, it won't appear in future searches
        projection_builder = ProjectionBuilder(projections_path)
        rows = projection_builder.get_all_transactions(include_duplicates=False)

        # Convert projection dicts to Transaction objects
        for row in rows:
            txn = Transaction.from_projection_row(row)
            transactions.append(txn)

        # Sort by date for efficient comparison
        transactions.sort(key=lambda t: (t.date, t.account_id, t.transaction_id))
        return transactions

    def find_potential_duplicates(
        self,
        transactions: list[Transaction],
        max_days_apart: int = 1,
        amount_tolerance: float = 0.001,
    ) -> list[TransactionPair]:
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
        pairs: list[TransactionPair] = []

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
                        txn1_source_file=txn1.source_file,
                        txn2_id=txn2.transaction_id,
                        txn2_date=txn2.date,
                        txn2_description=txn2.description,
                        txn2_amount=txn2.amount,
                        txn2_account=txn2.account_id,
                        txn2_source_file=txn2.source_file,
                    )
                )

        return pairs

    def assess_duplicate(self, pair: TransactionPair) -> DuplicateAssessment:
        """Use ML or LLM to assess if a transaction pair is a duplicate.

        Args:
            pair: Transaction pair to analyze

        Returns:
            Assessment with is_duplicate, confidence, and reasoning
        """
        # Try ML first if enabled and available
        if self.use_ml and self._ml_classifier is not None:
            try:
                return self._ml_classifier.predict(pair)
            except Exception:
                # Fall back to LLM if ML fails
                pass

        # Fall back to LLM
        return self._assess_duplicate_llm(pair)

    def _assess_duplicate_llm(self, pair: TransactionPair) -> DuplicateAssessment:
        """Use LLM to assess if a transaction pair is a duplicate.

        Args:
            pair: Transaction pair to analyze

        Returns:
            Assessment with is_duplicate, confidence, and reasoning
        """
        llm = self._get_llm()

        # Build prompt template with learned patterns
        if self.prompt_manager:
            prompt_template = self.prompt_manager.get_prompt()
        else:
            # Build adaptive prompt with learned patterns
            prompt_parts = [
                """You are analyzing bank transactions to detect duplicates.

Banks sometimes modify transaction descriptions over time - they may add """
                """suffixes, remove details, or reformat text. Your job is to determine """
                """if two transactions are likely the same transaction recorded twice """
                """(a duplicate) or two separate legitimate transactions.

Consider:
- Date proximity (same day or very close = more likely duplicate)
- Amount exactness (same amount = strong duplicate signal)
- Description similarity (accounting for bank's text variations)
- Account matching (same account = more likely duplicate)

Be conservative: when in doubt about whether transactions are duplicates, """
                """mark is_duplicate=false and explain your uncertainty in the reasoning."""
            ]

            # Add learned patterns if available
            if self.learned_patterns:
                prompt_parts.append("\n\nLearned patterns from previous feedback:")
                for pattern in self.learned_patterns:
                    prompt_parts.append(f"- {pattern}")

            prompt_parts.append("""\n\nAnalyze these two transactions:

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

Assess whether these are duplicates.""")

            prompt_template = "".join(prompt_parts)

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

    def scan_transactions(
        self,
        transactions: list[Transaction],
        max_days_apart: int = 1,
        amount_tolerance: float = 0.001,
    ) -> list[DuplicateMatch]:
        """Scan a list of transactions for duplicates.

        Args:
            transactions: List of transactions to scan
            max_days_apart: Maximum days between potential duplicates
            amount_tolerance: Acceptable difference in amounts

        Returns:
            List of detected duplicate matches with confidence scores
        """
        candidate_pairs = self.find_potential_duplicates(
            transactions, max_days_apart, amount_tolerance
        )

        matches: list[DuplicateMatch] = []
        for pair in candidate_pairs:
            assessment = self.assess_duplicate(pair)
            match = DuplicateMatch(pair=pair, assessment=assessment)
            matches.append(match)

        # Sort by confidence (highest first) for better user experience
        matches.sort(key=lambda m: m.assessment.confidence, reverse=True)
        return matches

    def scan_for_duplicates(
        self,
        data_dir: Path,
        max_days_apart: int = 1,
        amount_tolerance: float = 0.001,
    ) -> list[DuplicateMatch]:
        """Scan all ledgers for duplicate transactions.

        Args:
            data_dir: Directory containing ledger CSV files
            max_days_apart: Maximum days between potential duplicates (default 1)
            amount_tolerance: Acceptable difference in amounts (default 0.001)

        Returns:
            List of detected duplicate matches with confidence scores
        """
        transactions = self.load_all_transactions(data_dir)
        return self.scan_transactions(transactions, max_days_apart, amount_tolerance)


__all__ = ["DuplicateDetector"]
