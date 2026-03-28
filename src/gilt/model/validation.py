from __future__ import annotations

"""Base validation result types shared across services."""

from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Base result for validation operations."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)


__all__ = ["ValidationResult"]
