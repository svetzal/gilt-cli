from __future__ import annotations

"""
Duplicate detection models for transaction comparison using LLM-based analysis.

These models support structured output from LLMs to assess whether two transactions
are likely duplicates, accounting for variations in description text that banks may
apply over time.

Privacy:
- Models hold comparison results but do not perform network I/O themselves.
- Comparison is done via local LLM inference (via mojentic).
"""

from datetime import date
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class TransactionPair(BaseModel):
    """A pair of transactions being compared for duplication."""

    txn1_id: str
    txn1_date: date
    txn1_description: str
    txn1_amount: float
    txn1_account: str

    txn2_id: str
    txn2_date: date
    txn2_description: str
    txn2_amount: float
    txn2_account: str


class DuplicateAssessment(BaseModel):
    """Structured LLM output for duplicate detection.

    The LLM analyzes two transactions and returns:
    - is_duplicate: boolean judgment
    - confidence: 0.0-1.0 score of how confident the assessment is
    - reasoning: brief explanation of the decision
    """

    is_duplicate: bool = Field(
        description="Whether these two transactions appear to be duplicates"
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="Confidence level from 0.0 (not confident) to 1.0 (very confident)",
    )
    reasoning: str = Field(
        description="Brief explanation of why these are or aren't duplicates"
    )

    @field_validator("confidence", mode="before")
    @classmethod
    def normalize_confidence(cls, v):
        """Convert confidence to 0-1 range if provided as percentage."""
        if isinstance(v, (int, float)) and v > 1.0:
            return v / 100.0
        return v


class DuplicateMatch(BaseModel):
    """A detected duplicate pair with assessment details."""

    pair: TransactionPair
    assessment: DuplicateAssessment

    @property
    def confidence_pct(self) -> float:
        """Return confidence as percentage for display."""
        return self.assessment.confidence * 100


__all__ = [
    "TransactionPair",
    "DuplicateAssessment",
    "DuplicateMatch",
]
