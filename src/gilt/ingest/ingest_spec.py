from __future__ import annotations

import textwrap
from pathlib import Path

from gilt.ingest import parse_file


def _write_csv(tmp_path: Path, content: str, filename: str = "test.csv") -> Path:
    p = tmp_path / filename
    p.write_text(textwrap.dedent(content).strip(), encoding="utf-8")
    return p


class DescribeParseFileAmountSign:
    """Amount sign handling during ingestion."""

    def it_should_keep_amounts_as_is_with_expenses_negative(self, tmp_path):
        csv = _write_csv(tmp_path, """\
            Date,Description,Amount
            2025-01-15,SAMPLE STORE,-42.50
            2025-01-20,DEPOSIT,100.00
        """)
        df = parse_file(csv, "MYBANK_CHQ", amount_sign="expenses_negative")
        amounts = df["amount"].tolist()
        assert amounts[0] == -42.50
        assert amounts[1] == 100.00

    def it_should_negate_amounts_with_expenses_positive(self, tmp_path):
        csv = _write_csv(tmp_path, """\
            Date,Description,Amount
            2025-01-15,SAMPLE STORE,42.50
            2025-01-20,PAYMENT,-100.00
        """)
        df = parse_file(csv, "MYBANK_CC", amount_sign="expenses_positive")
        amounts = df["amount"].tolist()
        assert amounts[0] == -42.50
        assert amounts[1] == 100.00

    def it_should_default_to_expenses_negative(self, tmp_path):
        csv = _write_csv(tmp_path, """\
            Date,Description,Amount
            2025-01-15,SAMPLE STORE,-42.50
        """)
        df = parse_file(csv, "MYBANK_CHQ")
        assert df["amount"].iloc[0] == -42.50

    def it_should_negate_amounts_preserving_transaction_id_stability(self, tmp_path):
        """Transaction IDs use the final (negated) amount, ensuring idempotency."""
        csv = _write_csv(tmp_path, """\
            Date,Description,Amount
            2025-01-15,SAMPLE STORE,42.50
        """)
        df = parse_file(csv, "MYBANK_CC", amount_sign="expenses_positive")
        # Re-parse should produce the same transaction_id
        df2 = parse_file(csv, "MYBANK_CC", amount_sign="expenses_positive")
        assert df["transaction_id"].iloc[0] == df2["transaction_id"].iloc[0]
