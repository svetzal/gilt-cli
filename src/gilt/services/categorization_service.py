"""
Categorization service - functional core for categorization operations.

This service extracts categorization business logic from CLI commands,
making it testable without UI dependencies. It handles:
- Category validation
- Finding matching transactions
- Planning categorization operations
- Applying categorization to transactions

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. All functions return data structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gilt.model.account import TransactionGroup
from gilt.model.category import CategoryConfig
from gilt.model.events import TransactionCategorized
from gilt.services.transaction_operations_service import (
    SearchCriteria,
    TransactionOperationsService,
)

try:
    from gilt.storage.event_store import EventStore
except ImportError:
    EventStore = None  # type: ignore


@dataclass
class ValidationResult:
    """Result of validating a category/subcategory."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


@dataclass
class CategorizationPlan:
    """Plan for a categorization operation.

    Contains matched transactions, target category, and validation status.
    """

    matches: list[TransactionGroup]
    category: str
    subcategory: str | None
    is_valid: bool
    validation_errors: list[str] = field(default_factory=list)


@dataclass
class CategorizationResult:
    """Result of applying categorization to transactions."""

    updated_transactions: list[TransactionGroup]
    count: int
    errors: list[str] = field(default_factory=list)


class CategorizationService:
    """
    Service for categorization operations.

    This is the functional core - pure business logic with no I/O or UI dependencies.

    Responsibilities:
    - Validate category/subcategory exists in config
    - Find transactions matching criteria
    - Plan categorization operations with validation
    - Apply categorization to transactions

    Does NOT:
    - Display anything to console
    - Read from files directly
    - Prompt users for input
    - Format output for display
    """

    def __init__(
        self,
        category_config: CategoryConfig,
        transaction_service: TransactionOperationsService | None = None,
        event_store: EventStore | None = None,
    ):
        """
        Initialize categorization service.

        Args:
            category_config: Category configuration for validation
            transaction_service: Optional transaction operations service
                                (created if not provided)
            event_store: Optional event store for tracking categorization events.
                        If provided, emits TransactionCategorized events for ML training.
        """
        self._category_config = category_config
        self._transaction_service = transaction_service or TransactionOperationsService()
        self._event_store = event_store

    def validate_category(
        self, category: str, subcategory: str | None = None
    ) -> ValidationResult:
        """
        Validate that a category (and optional subcategory) exists in config.

        Args:
            category: Category name to validate
            subcategory: Optional subcategory name to validate

        Returns:
            ValidationResult with is_valid flag and error messages
        """
        # Normalize empty string to None for subcategory
        if subcategory is not None and subcategory.strip() == "":
            subcategory = None

        # Find category
        cat = self._category_config.find_category(category)
        if not cat:
            return ValidationResult(
                is_valid=False,
                errors=[f"Category '{category}' not found in config"],
            )

        # If subcategory specified, validate it exists
        if subcategory is not None and not cat.has_subcategory(subcategory):
            return ValidationResult(
                is_valid=False,
                errors=[f"Subcategory '{subcategory}' not found in category '{category}'"],
            )

        return ValidationResult(is_valid=True, errors=[])

    def find_matching_transactions(
        self,
        criteria: SearchCriteria,
        groups: list[TransactionGroup],
    ) -> list[TransactionGroup]:
        """
        Find transactions matching search criteria.

        Uses TransactionOperationsService for the actual matching logic.

        Args:
            criteria: Search criteria
            groups: List of transaction groups to search

        Returns:
            List of matching transaction groups
        """
        preview = self._transaction_service.find_by_criteria(criteria, groups)

        # Handle invalid pattern
        if preview.invalid_pattern:
            return []

        return preview.matched_groups

    def plan_categorization(
        self,
        criteria: SearchCriteria,
        groups: list[TransactionGroup],
        category: str,
        subcategory: str | None = None,
    ) -> CategorizationPlan:
        """
        Plan a categorization operation with validation.

        This finds matching transactions and validates the target category,
        but does NOT modify any data.

        Args:
            criteria: Search criteria for finding transactions
            groups: List of transaction groups to search
            category: Target category name
            subcategory: Optional target subcategory name

        Returns:
            CategorizationPlan with matches, target category, and validation status
        """
        # Find matching transactions
        matches = self.find_matching_transactions(criteria, groups)

        # Validate target category
        validation = self.validate_category(category, subcategory)

        return CategorizationPlan(
            matches=matches,
            category=category,
            subcategory=subcategory,
            is_valid=validation.is_valid,
            validation_errors=validation.errors,
        )

    def apply_categorization(
        self,
        matches: list[TransactionGroup],
        category: str,
        subcategory: str | None = None,
    ) -> CategorizationResult:
        """
        Apply categorization to a list of transaction groups.

        This creates NEW transaction groups with updated category/subcategory.
        Original groups are NOT modified.

        If an event_store was provided at initialization, emits TransactionCategorized
        events for ML training data.

        Args:
            matches: List of transaction groups to categorize
            category: Target category name
            subcategory: Optional target subcategory name

        Returns:
            CategorizationResult with updated transactions and count
        """
        updated: list[TransactionGroup] = []

        for group in matches:
            # Store previous categorization for event
            prev_category = group.primary.category
            prev_subcategory = group.primary.subcategory

            # Create new transaction with updated category/subcategory
            updated_txn = group.primary.model_copy(
                update={
                    "category": category,
                    "subcategory": subcategory,
                }
            )

            # Create new group with updated transaction
            updated_group = TransactionGroup(
                group_id=group.group_id,
                primary=updated_txn,
                splits=group.splits,
            )

            updated.append(updated_group)

            # Emit event for ML training if event store available
            if self._event_store:
                self._emit_categorization_event(
                    transaction=updated_txn,
                    previous_category=prev_category,
                    previous_subcategory=prev_subcategory,
                )

        return CategorizationResult(
            updated_transactions=updated,
            count=len(updated),
            errors=[],
        )

    def _emit_categorization_event(
        self,
        transaction,
        previous_category: str | None,
        previous_subcategory: str | None,
    ) -> None:
        """
        Emit TransactionCategorized event to event store.

        This creates training data for auto-categorization ML models.

        Args:
            transaction: The categorized transaction
            previous_category: Previous category (None if first-time categorization)
            previous_subcategory: Previous subcategory
        """
        event = TransactionCategorized(
            transaction_id=transaction.transaction_id,
            category=transaction.category or "",
            subcategory=transaction.subcategory,
            source="user",  # Manual categorization via CLI/GUI
            confidence=None,  # User categorization has no confidence score
            previous_category=previous_category,
            previous_subcategory=previous_subcategory,
            rationale=None,  # Could be enhanced to capture user notes
        )
        self._event_store.append_event(event)


__all__ = [
    "CategorizationService",
    "ValidationResult",
    "CategorizationPlan",
    "CategorizationResult",
]
