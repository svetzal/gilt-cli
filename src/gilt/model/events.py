"""
Event sourcing models for Finance application.

This module defines immutable event types that represent all state changes
in the system. Events are append-only and form the source of truth.

All events inherit from the base Event class and include:
- Automatic event_id generation (UUID)
- Automatic event_timestamp
- JSON serialization/deserialization via Pydantic v2
- Aggregate type and ID for event stream grouping

Privacy: Events contain sensitive financial data and should never be
transmitted over networks. All processing is local-only.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field, field_serializer, field_validator


class Event(BaseModel):
    """Base event class for all event types.

    All events are immutable and timestamped. Events form an append-only log
    that serves as the source of truth for the system state.
    """

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_type: str
    event_timestamp: datetime = Field(default_factory=datetime.now)
    aggregate_type: Optional[str] = None
    aggregate_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_serializer("event_timestamp")
    def serialize_timestamp(self, value: datetime) -> str:
        """Serialize datetime to ISO format string."""
        return value.isoformat()

    @field_validator("event_timestamp", mode="before")
    @classmethod
    def parse_timestamp(cls, value: Any) -> datetime:
        """Parse timestamp from string or datetime."""
        if isinstance(value, str):
            return datetime.fromisoformat(value)
        return value


class TransactionImported(Event):
    """Event emitted when a transaction is imported from CSV.

    This event captures the raw transaction data exactly as it appears in the
    source CSV file. The transaction_id is deterministic (hash of key fields)
    to enable idempotent imports.
    """

    event_type: str = Field(default="TransactionImported", frozen=True)
    aggregate_type: str = Field(default="transaction", frozen=True)

    transaction_date: str  # ISO format YYYY-MM-DD
    transaction_id: str  # Deterministic hash
    source_file: str
    source_account: str
    raw_description: str
    amount: Decimal
    currency: str = "CAD"
    raw_data: Dict[str, Any]  # Complete CSV row for reconstruction
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to transaction_id."""
        if "aggregate_id" not in data and "transaction_id" in data:
            data["aggregate_id"] = data["transaction_id"]
        super().__init__(**data)

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        """Serialize Decimal to string to preserve precision."""
        return str(value)

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: Any) -> Decimal:
        """Parse amount from string or number."""
        if isinstance(value, str):
            return Decimal(value)
        return Decimal(str(value))


class TransactionDescriptionObserved(Event):
    """Event emitted when the same transaction appears with a different description.

    Banks sometimes modify transaction descriptions in later exports (e.g., adding
    province codes, reference numbers). This event tracks the evolution of
    descriptions for the same underlying transaction.
    """

    event_type: str = Field(default="TransactionDescriptionObserved", frozen=True)
    aggregate_type: str = Field(default="transaction", frozen=True)

    original_transaction_id: str
    new_transaction_id: str  # Different due to description change
    transaction_date: str  # ISO format
    original_description: str
    new_description: str
    source_file: str
    source_account: str
    amount: Decimal
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to original_transaction_id."""
        if "aggregate_id" not in data and "original_transaction_id" in data:
            data["aggregate_id"] = data["original_transaction_id"]
        super().__init__(**data)

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return str(value)

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: Any) -> Decimal:
        if isinstance(value, str):
            return Decimal(value)
        return Decimal(str(value))


class DuplicateSuggested(Event):
    """Event emitted when LLM suggests two transactions might be duplicates.

    Captures the LLM's assessment including confidence score, reasoning,
    and detailed comparison. This forms training data for improving
    duplicate detection accuracy.

    The assessment field must include:
    - is_duplicate: bool
    - confidence: float
    - reasoning: str
    - pair: Complete TransactionPair data (all transaction fields for both)

    The pair data enables ML training without additional database queries.
    """

    event_type: str = Field(default="DuplicateSuggested", frozen=True)
    aggregate_type: str = Field(default="duplicate", frozen=True)

    transaction_id_1: str
    transaction_id_2: str
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str
    model: str  # LLM model used
    prompt_version: str  # Version of prompt template
    assessment: Dict[str, Any]  # Includes 'pair' with complete TransactionPair data
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to combination of transaction IDs."""
        if "aggregate_id" not in data and "transaction_id_1" in data and "transaction_id_2" in data:
            t1 = data["transaction_id_1"]
            t2 = data["transaction_id_2"]
            data["aggregate_id"] = f"{min(t1, t2)}:{max(t1, t2)}"
        super().__init__(**data)


class DuplicateConfirmed(Event):
    """Event emitted when user confirms a duplicate suggestion.

    Captures the user's decision including which transaction to keep as primary
    and their preferred description format. This is valuable ML training data.
    """

    event_type: str = Field(default="DuplicateConfirmed", frozen=True)
    aggregate_type: str = Field(default="duplicate", frozen=True)

    suggestion_event_id: str  # Links to DuplicateSuggested
    primary_transaction_id: str  # Keep this one
    duplicate_transaction_id: str  # Mark as duplicate
    canonical_description: str  # User's preferred description
    user_rationale: Optional[str] = None
    llm_was_correct: bool
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to combination of transaction IDs."""
        if (
            "aggregate_id" not in data
            and "primary_transaction_id" in data
            and "duplicate_transaction_id" in data
        ):
            t1 = data["primary_transaction_id"]
            t2 = data["duplicate_transaction_id"]
            data["aggregate_id"] = f"{min(t1, t2)}:{max(t1, t2)}"
        super().__init__(**data)


class DuplicateRejected(Event):
    """Event emitted when user rejects a duplicate suggestion.

    Negative feedback is crucial for improving LLM accuracy. Captures why
    the user believes these are separate transactions.
    """

    event_type: str = Field(default="DuplicateRejected", frozen=True)
    aggregate_type: str = Field(default="duplicate", frozen=True)

    suggestion_event_id: str
    transaction_id_1: str
    transaction_id_2: str
    user_rationale: Optional[str] = None
    llm_was_correct: bool
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to combination of transaction IDs."""
        if "aggregate_id" not in data and "transaction_id_1" in data and "transaction_id_2" in data:
            t1 = data["transaction_id_1"]
            t2 = data["transaction_id_2"]
            data["aggregate_id"] = f"{min(t1, t2)}:{max(t1, t2)}"
        super().__init__(**data)


class TransactionCategorized(Event):
    """Event emitted when a transaction is categorized.

    Tracks who/what assigned the category (user, LLM, or rule) and the
    previous category for undo capability.
    """

    event_type: str = Field(default="TransactionCategorized", frozen=True)
    aggregate_type: str = Field(default="transaction", frozen=True)

    transaction_id: str
    category: str
    subcategory: Optional[str] = None
    source: str = Field(pattern="^(user|llm|rule)$")  # How was this categorized
    confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    previous_category: Optional[str] = None
    previous_subcategory: Optional[str] = None
    rationale: Optional[str] = None
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to transaction_id."""
        if "aggregate_id" not in data and "transaction_id" in data:
            data["aggregate_id"] = data["transaction_id"]
        super().__init__(**data)


class CategorizationRuleCreated(Event):
    """Event emitted when user creates a categorization rule.

    Rules allow pattern-based automatic categorization. Events enable
    versioning and experimenting with different rule sets.
    """

    event_type: str = Field(default="CategorizationRuleCreated", frozen=True)
    aggregate_type: str = Field(default="rule", frozen=True)

    rule_id: str
    rule_type: str  # e.g., "description_pattern", "amount_range"
    pattern: str  # Regex or other matching pattern
    category: str
    subcategory: Optional[str] = None
    enabled: bool = True
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to rule_id."""
        if "aggregate_id" not in data and "rule_id" in data:
            data["aggregate_id"] = data["rule_id"]
        super().__init__(**data)


class BudgetCreated(Event):
    """Event emitted when user creates a budget.

    Budgets are versioned through events, enabling time-travel queries
    like "what was my transportation budget in October?"
    """

    event_type: str = Field(default="BudgetCreated", frozen=True)
    aggregate_type: str = Field(default="budget", frozen=True)

    budget_id: str
    category: str
    subcategory: Optional[str] = None
    period_type: str  # e.g., "monthly", "quarterly", "annual"
    start_date: str  # ISO format
    amount: Decimal
    currency: str = "CAD"
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to budget_id."""
        if "aggregate_id" not in data and "budget_id" in data:
            data["aggregate_id"] = data["budget_id"]
        super().__init__(**data)

    @field_serializer("amount")
    def serialize_amount(self, value: Decimal) -> str:
        return str(value)

    @field_validator("amount", mode="before")
    @classmethod
    def parse_amount(cls, value: Any) -> Decimal:
        if isinstance(value, str):
            return Decimal(value)
        return Decimal(str(value))


class BudgetUpdated(Event):
    """Event emitted when user updates an existing budget.

    Tracks changes to budget amount, period, or effective date.
    Previous values are captured for audit trail.
    """

    event_type: str = Field(default="BudgetUpdated", frozen=True)
    aggregate_type: str = Field(default="budget", frozen=True)

    budget_id: str
    category: str
    subcategory: Optional[str] = None
    new_amount: Optional[Decimal] = None
    previous_amount: Optional[Decimal] = None
    new_period_type: Optional[str] = None
    previous_period_type: Optional[str] = None
    new_start_date: Optional[str] = None  # ISO format
    previous_start_date: Optional[str] = None
    currency: str = "CAD"
    rationale: Optional[str] = None  # Why the change was made
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to budget_id."""
        if "aggregate_id" not in data and "budget_id" in data:
            data["aggregate_id"] = data["budget_id"]
        super().__init__(**data)

    @field_serializer("new_amount", "previous_amount")
    def serialize_amount(self, value: Optional[Decimal]) -> Optional[str]:
        return str(value) if value is not None else None

    @field_validator("new_amount", "previous_amount", mode="before")
    @classmethod
    def parse_amount(cls, value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, str):
            return Decimal(value)
        return Decimal(str(value))


class BudgetDeleted(Event):
    """Event emitted when user deletes a budget.

    Soft delete - budget is marked as deleted but historical data preserved.
    Can be used to track budget lifecycle.
    """

    event_type: str = Field(default="BudgetDeleted", frozen=True)
    aggregate_type: str = Field(default="budget", frozen=True)

    budget_id: str
    category: str
    subcategory: Optional[str] = None
    final_amount: Decimal  # Last known amount before deletion
    final_period_type: str
    final_start_date: str  # ISO format
    currency: str = "CAD"
    rationale: Optional[str] = None  # Why it was deleted
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to budget_id."""
        if "aggregate_id" not in data and "budget_id" in data:
            data["aggregate_id"] = data["budget_id"]
        super().__init__(**data)

    @field_serializer("final_amount")
    def serialize_amount(self, value: Decimal) -> str:
        return str(value)

    @field_validator("final_amount", mode="before")
    @classmethod
    def parse_amount(cls, value: Any) -> Decimal:
        if isinstance(value, str):
            return Decimal(value)
        return Decimal(str(value))


class TransactionEnriched(Event):
    """Event emitted when a transaction is enriched with receipt/invoice data.

    Captures structured data from email receipts (JSON sidecar files) that
    provide vendor details, invoice numbers, tax breakdowns, and links to
    PDF receipts. If multiple enrichments exist for one transaction, the
    latest event wins during projection.
    """

    event_type: str = Field(default="TransactionEnriched", frozen=True)
    aggregate_type: str = Field(default="transaction", frozen=True)

    transaction_id: str  # Links to existing transaction
    vendor: str  # Proper company name, e.g. 'Zoom Communications, Inc.'
    service: Optional[str] = None  # Specific product/plan
    invoice_number: Optional[str] = None
    tax_amount: Optional[Decimal] = None
    tax_type: Optional[str] = None  # e.g. 'HST', 'GST', None
    currency: str = "CAD"
    receipt_file: Optional[str] = None  # Relative path to PDF
    enrichment_source: str  # Path to the JSON file that provided this data
    source_email: Optional[str] = None  # Sender address from receipt email
    match_confidence: Optional[str] = None  # "exact", "fx-adjusted", "pattern-assisted"
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to transaction_id."""
        if "aggregate_id" not in data and "transaction_id" in data:
            data["aggregate_id"] = data["transaction_id"]
        super().__init__(**data)

    @field_serializer("tax_amount")
    def serialize_tax_amount(self, value: Optional[Decimal]) -> Optional[str]:
        return str(value) if value is not None else None

    @field_validator("tax_amount", mode="before")
    @classmethod
    def parse_tax_amount(cls, value: Any) -> Optional[Decimal]:
        if value is None:
            return None
        if isinstance(value, str):
            return Decimal(value)
        return Decimal(str(value))


class PromptUpdated(Event):
    """Event emitted when adaptive prompt learning updates the prompt.

    Tracks learned patterns from user feedback and accuracy metrics
    across versions. Enables A/B testing and rollback.
    """

    event_type: str = Field(default="PromptUpdated", frozen=True)
    aggregate_type: str = Field(default="prompt", frozen=True)

    prompt_version: str
    previous_version: Optional[str] = None
    learned_patterns: List[str]
    accuracy_metrics: Dict[str, Any]
    aggregate_id: Optional[str] = None

    def __init__(self, **data):
        """Initialize and set aggregate_id to prompt_version."""
        if "aggregate_id" not in data and "prompt_version" in data:
            data["aggregate_id"] = data["prompt_version"]
        super().__init__(**data)


__all__ = [
    "Event",
    "TransactionImported",
    "TransactionDescriptionObserved",
    "DuplicateSuggested",
    "DuplicateConfirmed",
    "DuplicateRejected",
    "TransactionCategorized",
    "TransactionEnriched",
    "CategorizationRuleCreated",
    "BudgetCreated",
    "BudgetUpdated",
    "BudgetDeleted",
    "PromptUpdated",
]
