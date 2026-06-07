"""Merchant name normalizer for transaction descriptions.

Strips noise tokens (store numbers, reference codes, cities, FX tails, etc.)
from raw bank descriptions so that variants of the same merchant resolve
to a single canonical key, suitable for rule lookup and TF-IDF features.

This module is pure (no I/O) and order-sensitive: each regex pass runs on
the output of the previous one.
"""

from __future__ import annotations

import re

# Two-letter Canadian province codes used for trailing city/province stripping.
_PROVINCE_CODES = frozenset(
    {
        "AB",
        "BC",
        "MB",
        "NB",
        "NL",
        "NS",
        "NT",
        "NU",
        "ON",
        "PE",
        "QC",
        "SK",
        "YT",
    }
)

# Noise prefixes that precede the real merchant name.
_NOISE_PREFIXES = re.compile(
    r"^(?:"
    r"E-TRANSFER\s+(?:SENT|RECEIVED)\s+"
    r"|POS\s+PURCHASE\s+"
    r"|POINT\s+OF\s+SALE\s+"
    r"|PURCHASE\s+"
    r")",
    re.IGNORECASE,
)

# FX tail: e.g. "- 87.86 USD @ 1.416913" or "87.86 USD @ 1.4"
_FX_TAIL = re.compile(
    r"\s*-?\s*[\d,]+\.?\d*\s*[A-Z]{3}\s*@\s*[\d.]+\s*$",
    re.IGNORECASE,
)

# Store/branch number tokens attached to or following the merchant name.
_STORE_NUMBER = re.compile(
    r"(?:"
    r"\*[A-Z0-9]{4,}"  # *BC0BQ7RY2 (Amazon-style, attached or separated)
    r"|@\s*\d+"  # @4268 or @ 4268
    r"|#\s*\d+"  # #1234, # 104781
    r")",
    re.IGNORECASE,
)

# Multiple spaces
_MULTI_SPACE = re.compile(r"\s{2,}")


def _strip_trailing_ref_code(text: str) -> str:
    """Strip a single trailing token that looks like a reference/auth code.

    A ref code is an uppercase alphanumeric token of 5+ characters that
    contains at least one digit (to distinguish from merchant abbreviations
    like LTD, CORP, INC).
    """
    tokens = text.split()
    if not tokens:
        return text
    last = tokens[-1]
    # Must be all uppercase alphanumeric, ≥5 chars, and contain at least one digit
    if len(last) >= 5 and re.match(r"^[A-Z0-9]+$", last) and any(c.isdigit() for c in last):
        return " ".join(tokens[:-1])
    return text


def _strip_trailing_province(text: str) -> str:
    """Remove a trailing Canadian province code (exactly 2 uppercase letters)."""
    tokens = text.split()
    if tokens and tokens[-1].upper() in _PROVINCE_CODES:
        return " ".join(tokens[:-1])
    return text


def _strip_one_trailing_city_token(text: str) -> str:
    """Remove one trailing pure-alpha uppercase token of 4+ chars (likely a city name).

    Called after a separator (store number or FX tail) was stripped — the
    separator means the last remaining token is likely a geographic suffix
    (e.g. CAMBRIDGE, TORONTO, HALIBURTON, MILLERTON).

    Short tokens (≤3 chars) and tokens with digits are never stripped here,
    to protect abbreviations like "CA" or merchant suffixes like "LTD".
    """
    tokens = text.split()
    if not tokens:
        return text
    last = tokens[-1]
    # Pure uppercase alpha, 4+ chars → looks like a city token
    if len(last) >= 4 and re.match(r"^[A-Z]+$", last):
        return " ".join(tokens[:-1])
    return text


def normalize_merchant(description: str) -> str:
    """Normalize a raw bank transaction description to a canonical merchant key.

    Applies layered, order-sensitive transformations:
    1. Strip noise prefixes (E-TRANSFER SENT, POS PURCHASE, etc.)
    2. Strip FX conversion tails; also strip trailing city before the tail
    3. Strip store/branch numbers (#1234, @4268, *BC0BQ7RY2)
    4. Strip trailing reference/auth codes (alphanumeric hash tokens)
    5. Strip trailing province code, then city token if a separator was removed
    6. Lowercase and collapse whitespace

    Args:
        description: Raw transaction description from bank CSV.

    Returns:
        Lowercase canonical merchant string, or "" for empty input.
    """
    if not description or not description.strip():
        return ""

    text = description.strip()

    # 1. Strip noise prefixes (e-transfer, POS purchase, etc.)
    text = _NOISE_PREFIXES.sub("", text).strip()

    # 2. Strip FX conversion tail; if one was present, also remove any trailing
    #    city token that sat just before the FX separator (e.g. "MILLERTON").
    fx_stripped, n_fx = _FX_TAIL.subn("", text)
    text = fx_stripped.strip()
    if n_fx > 0:
        text = _strip_one_trailing_city_token(text).strip()

    # 3. Strip store/branch numbers. Track whether a substitution occurred —
    #    if so, a trailing city may have been revealed after the store number.
    stripped_store, n_store = _STORE_NUMBER.subn(" ", text)
    store_number_was_stripped = n_store > 0
    text = stripped_store.strip()

    # 4. Collapse multiple spaces introduced by removals
    text = _MULTI_SPACE.sub(" ", text).strip()

    # 5. Strip trailing reference/auth codes (loop to handle stacked codes).
    #    Only strips tokens that contain at least one digit — avoids stripping
    #    uppercase merchant words like LTD, CORP, INC.
    for _ in range(3):
        cleaned = _strip_trailing_ref_code(text)
        if cleaned == text:
            break
        text = cleaned

    # 6. Strip trailing province code (always safe — province codes are never merchants).
    text = _strip_trailing_province(text)

    # 7. Strip one trailing city token only when a store-number separator was
    #    present (the separator marks the boundary between merchant and city).
    if store_number_was_stripped:
        text = _strip_one_trailing_city_token(text)

    # 8. Collapse whitespace, lowercase, strip edge punctuation
    text = _MULTI_SPACE.sub(" ", text).strip()
    text = text.strip("-_ ./").strip()
    text = text.lower()

    return text


def is_income_category(path: str) -> bool:
    """Return True if the category path's top-level component is 'income'.

    Args:
        path: Category path string like "Income:Salary" or "income"

    Returns:
        True when the first path component is "income" (case-insensitive).
    """
    if not path:
        return False
    top_level = path.split(":")[0].strip()
    return top_level.lower() == "income"


__all__ = ["normalize_merchant", "is_income_category"]
