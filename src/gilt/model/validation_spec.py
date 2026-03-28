from __future__ import annotations

"""Specs for the shared ValidationResult base type."""

from gilt.model.validation import ValidationResult


class DescribeValidationResult:
    def it_should_be_valid_with_no_errors(self):
        result = ValidationResult(is_valid=True)
        assert result.is_valid is True
        assert result.errors == []

    def it_should_be_invalid_when_errors_present(self):
        result = ValidationResult(is_valid=False, errors=["something went wrong"])
        assert result.is_valid is False
        assert len(result.errors) == 1
