"""
Service layer for Finance application.

This module contains the functional core business logic separated from
imperative shell (CLI/GUI). Services are pure business logic with no I/O
or side effects.

Principles:
- No UI framework imports (Rich, Typer, Qt)
- All dependencies injected through constructors
- Functions return data structures, not void
- Fully testable with simple unit tests
"""

from finance.services.duplicate_review_service import (
    DuplicateReviewService,
    ReviewSummary,
    UserDecision,
    SmartDefault,
)
from finance.services.budget_service import (
    BudgetService,
    BudgetItem,
    BudgetSummary,
)
from finance.services.category_management_service import (
    CategoryManagementService,
    CategoryUsage,
    RemovalPlan,
    AdditionResult,
    BudgetUpdateResult,
)
from finance.services.duplicate_service import DuplicateService
from finance.services.smart_category_service import SmartCategoryService

__all__ = [
    "DuplicateReviewService",
    "ReviewSummary",
    "UserDecision",
    "SmartDefault",
    "BudgetService",
    "BudgetItem",
    "BudgetSummary",
    "CategoryManagementService",
    "CategoryUsage",
    "RemovalPlan",
    "AdditionResult",
    "BudgetUpdateResult",
    "DuplicateService",
    "SmartCategoryService",
]
