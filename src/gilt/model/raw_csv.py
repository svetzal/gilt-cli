from pathlib import Path

import pandas as pd


def read_raw_csv(path: Path, *, nrows: int | None = None) -> pd.DataFrame:
    """Read a raw bank-export CSV with consistent encoding and type settings.

    Forces all columns to string type and preserves empty strings (no NaN coercion).
    Handles UTF-8 BOM headers produced by many bank export tools.
    """
    return pd.read_csv(path, encoding="utf-8-sig", dtype=str, keep_default_na=False, nrows=nrows)


__all__ = ["read_raw_csv"]
