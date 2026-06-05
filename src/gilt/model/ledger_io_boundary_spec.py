from __future__ import annotations

import re
from pathlib import Path


class DescribeLedgerIoBoundary:
    """Guard: no raw pandas ledger I/O outside approved modules."""

    _ALLOWED_SUFFIXES = frozenset({
        "model/raw_csv.py",         # raw bank export reads (not ledger I/O)
        "model/ledger_io.py",       # pure serialisation, no disk I/O
        "model/ledger_repository.py",  # gateway (uses read_text/write_text, not pandas)
    })
    _PATTERNS = [re.compile(r"pd\.read_csv"), re.compile(r"\.to_csv\(")]

    def it_should_have_no_raw_pandas_ledger_access_outside_approved_modules(self):
        src_root = Path(__file__).parent.parent  # src/gilt/
        violations: list[str] = []
        for py_file in sorted(src_root.rglob("*.py")):
            if py_file.name.endswith("_spec.py") or py_file.name == "conftest.py":
                continue
            rel = py_file.relative_to(src_root)
            if any(str(rel).endswith(suffix) for suffix in self._ALLOWED_SUFFIXES):
                continue
            text = py_file.read_text(encoding="utf-8")
            for pat in self._PATTERNS:
                if pat.search(text):
                    violations.append(f"{rel}: {pat.pattern}")
        assert violations == [], "Raw pandas ledger I/O found:\n" + "\n".join(violations)
