from __future__ import annotations

"""
Fiscal year utilities for Gilt.

Mojility fiscal year: November 1 → October 31.
FY25 means Nov 1 2024 – Oct 31 2025.
"""

import re
from datetime import date

_FY_PATTERN = re.compile(r"^[Ff][Yy](\d{2}|\d{4})$")


def fiscal_year_range(year_arg: str) -> tuple[date, date]:
    """Return the inclusive (start, end) date range for a fiscal year string.

    Accepts formats: ``FY25``, ``fy25``, ``FY2025``, ``fy2025`` (case-insensitive).
    The fiscal year runs from November 1 of year−1 through October 31 of year.

    Args:
        year_arg: Fiscal year string, e.g. ``"FY25"`` or ``"FY2025"``.

    Returns:
        A ``(start_date, end_date)`` tuple, both inclusive.

    Raises:
        ValueError: If the string does not match the expected format.
    """
    match = _FY_PATTERN.match(year_arg.strip())
    if not match:
        raise ValueError(
            f"Invalid fiscal year format: {year_arg!r}. "
            "Expected FY25, fy25, FY2025, or fy2025."
        )
    digits = match.group(1)
    year = 2000 + int(digits) if len(digits) == 2 else int(digits)

    start = date(year - 1, 11, 1)
    end = date(year, 10, 31)
    return start, end


__all__ = ["fiscal_year_range"]
