from __future__ import annotations

"""Pure ISO-date parsing and formatting helpers.

All CLI YYYY-MM-DD input parsing and formatting routes through these functions
so the expected format string and error wording live in exactly one place.
"""

from datetime import date


def parse_iso_date(value: str) -> date:
    """Parse a YYYY-MM-DD string into a ``date``.

    Raises:
        ValueError: If ``value`` is not a valid ISO date, with a message that
            includes both the offending value and the text ``Expected YYYY-MM-DD``.
    """
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise ValueError(f"Invalid date value: {value!r}. Expected YYYY-MM-DD") from None


def format_iso_date(d: date) -> str:
    """Format a ``date`` as a YYYY-MM-DD string."""
    return d.isoformat()


__all__ = ["parse_iso_date", "format_iso_date"]
