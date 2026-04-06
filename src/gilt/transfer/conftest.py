from __future__ import annotations

from pathlib import Path

import pandas as pd


def write_ledger_from_dicts(path: Path, rows: list[dict]):
    df = pd.DataFrame(rows)
    df.to_csv(path, index=False)
