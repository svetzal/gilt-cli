"""
Transaction operations service - functional core for transaction manipulation.

This service extracts transaction finding and manipulation logic from CLI commands,
making it testable without UI dependencies. It handles:
- Finding transactions by ID prefix
- Finding transactions by search criteria (description, pattern, amount)
- Adding notes to transactions
- Previewing batch operations

NO IMPORTS FROM:
- rich (console, table, prompt)
- typer
- PySide6/Qt

All dependencies are injected. All functions return data structures.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum

from gilt.model.account import TransactionGroup


class NoteMode(StrEnum):
    """Mode for adding notes to transactions."""

    REPLACE = "replace"
    APPEND = "append"
    PREPEND = "prepend"


@dataclass
class SearchCriteria:
    """Criteria for finding transactions."""

    description: str | None = None
    desc_prefix: str | None = None
    pattern: str | None = None  # Regex pattern string
    amount: float | None = None


@dataclass
class MatchResult:
    """Result of finding a transaction by ID prefix."""

    type: str  # "match", "ambiguous", "not_found"
    transaction: TransactionGroup | None = None
    matches: list[TransactionGroup] | None = None  # For ambiguous case

    @property
    def is_match(self) -> bool:
        return self.type == "match"

    @property
    def is_ambiguous(self) -> bool:
        return self.type == "ambiguous"

    @property
    def is_not_found(self) -> bool:
        return self.type == "not_found"


@dataclass
class BatchPreview:
    """Preview of a batch operation."""

    matched_groups: list[TransactionGroup]
    total_count: int
    criteria: SearchCriteria
    used_sign_insensitive: bool = False  # True if matched by absolute amount
    invalid_pattern: bool = False  # True if regex pattern was invalid


class TransactionOperationsService:
    """
    Service for transaction finding and manipulation operations.

    This is the functional core - pure business logic with no I/O or UI dependencies.

    Responsibilities:
    - Find transactions by ID prefix with exact/ambiguous/not found results
    - Find transactions by search criteria (description, prefix, pattern, amount)
    - Apply notes to transactions (replace/append/prepend modes)
    - Preview batch operations

    Does NOT:
    - Display anything to console
    - Read from files directly
    - Prompt users for input
    - Format output for display
    """

    def find_by_id_prefix(
        self,
        prefix: str,
        groups: list[TransactionGroup],
        min_length: int = 8,
    ) -> MatchResult:
        """
        Find transactions by ID prefix.

        Args:
            prefix: Transaction ID prefix (case-insensitive)
            groups: List of transaction groups to search
            min_length: Minimum prefix length required (default 8)

        Returns:
            MatchResult indicating:
            - match: Exactly one transaction found
            - ambiguous: Multiple transactions match
            - not_found: No transactions match
        """
        # Normalize and validate prefix
        normalized = (prefix or "").strip().lower()
        if len(normalized) < min_length:
            return MatchResult(type="not_found", matches=[])

        # Find all matches
        matches = [g for g in groups if g.primary.transaction_id.lower().startswith(normalized)]

        if len(matches) == 0:
            return MatchResult(type="not_found", matches=[])
        elif len(matches) == 1:
            return MatchResult(type="match", transaction=matches[0], matches=[])
        else:
            return MatchResult(type="ambiguous", matches=matches)

    @staticmethod
    def _matches_description(
        desc: str,
        criteria: SearchCriteria,
        compiled_pattern: re.Pattern | None,
    ) -> bool:
        """Check if a description matches the search criteria."""
        if criteria.description is not None:
            return desc == criteria.description.strip()
        elif criteria.desc_prefix is not None:
            return desc.lower().startswith(criteria.desc_prefix.strip().lower())
        elif compiled_pattern is not None:
            return bool(compiled_pattern.search(desc))
        return False

    def find_by_criteria(
        self,
        criteria: SearchCriteria,
        groups: list[TransactionGroup],
    ) -> BatchPreview:
        """Find transactions matching search criteria."""
        compiled_pattern: re.Pattern | None = None
        if criteria.pattern:
            try:
                compiled_pattern = re.compile(criteria.pattern, re.IGNORECASE)
            except re.error:
                return BatchPreview(
                    matched_groups=[], total_count=0, criteria=criteria,
                    used_sign_insensitive=False, invalid_pattern=True,
                )

        # Collect description-matching groups in one pass
        desc_matched: list[TransactionGroup] = []
        for group in groups:
            desc = (group.primary.description or "").strip()
            if self._matches_description(desc, criteria, compiled_pattern):
                desc_matched.append(group)

        # Filter by amount (signed first, then absolute fallback)
        if criteria.amount is None:
            return BatchPreview(
                matched_groups=desc_matched, total_count=len(desc_matched),
                criteria=criteria, used_sign_insensitive=False,
            )

        signed = [g for g in desc_matched if abs(g.primary.amount - criteria.amount) < 0.01]
        if signed:
            return BatchPreview(
                matched_groups=signed, total_count=len(signed),
                criteria=criteria, used_sign_insensitive=False,
            )

        absolute = [
            g for g in desc_matched
            if abs(abs(g.primary.amount) - abs(criteria.amount)) < 0.01
        ]
        return BatchPreview(
            matched_groups=absolute, total_count=len(absolute),
            criteria=criteria, used_sign_insensitive=bool(absolute),
        )

    def add_note(
        self,
        group: TransactionGroup,
        note_text: str,
        mode: NoteMode = NoteMode.REPLACE,
    ) -> TransactionGroup:
        """
        Add note to transaction.

        Args:
            group: Transaction group to modify
            note_text: Note text to add
            mode: How to add note (replace/append/prepend)

        Returns:
            New TransactionGroup with updated note
        """
        current_note = group.primary.notes or ""

        if mode == NoteMode.REPLACE:
            new_note = note_text
        elif mode == NoteMode.APPEND:
            new_note = f"{current_note} {note_text}" if current_note else note_text
        else:  # PREPEND
            new_note = f"{note_text} {current_note}" if current_note else note_text

        # Create new transaction with updated note
        updated_txn = group.primary.model_copy(update={"notes": new_note})

        # Create new group with updated transaction
        return TransactionGroup(
            group_id=group.group_id,
            primary=updated_txn,
            splits=group.splits,
        )

    def preview_batch_update(
        self,
        matches: list[TransactionGroup],
        note_text: str,
        mode: NoteMode = NoteMode.REPLACE,
    ) -> list[tuple[TransactionGroup, TransactionGroup]]:
        """
        Preview a batch note update operation.

        Args:
            matches: Groups to update
            note_text: Note text to add
            mode: How to add note

        Returns:
            List of (original_group, updated_group) tuples
        """
        previews = []
        for group in matches:
            updated = self.add_note(group, note_text, mode)
            previews.append((group, updated))
        return previews


__all__ = [
    "TransactionOperationsService",
    "SearchCriteria",
    "MatchResult",
    "BatchPreview",
    "NoteMode",
]
