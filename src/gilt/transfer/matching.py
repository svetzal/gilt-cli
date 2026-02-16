from __future__ import annotations

"""
Pure transfer matching logic (no CLI, no printing).

- Operates on per-account ledger CSVs under data/accounts/ (or a provided directory).
- Provides data structures and compute_matches() for use by other modules.
- Privacy-safe: does not print raw descriptions; hashing is available via Txn.desc_hash8 if needed by callers.
"""

from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

import pandas as pd

# Tokens and keywords used to assess transfer-like transactions
DESCRIPTION_TOKENS = [
    "INTERAC",
    "E-TRANSFER",
    "E TRANSFER",
    "E-TRF",
    "EMAIL MONEY TRANSFER",
    "EMT",
    "TRANSFER",
    "XFER",
    "MOVE FUNDS",
]
FEE_KEYWORDS = ["FEE", "SERVICE CHARGE", "INTERAC FEE"]
# Transactions with these tokens are not considered as transfer pairs (they may be attached as fees)
NONTRANSFER_TOKENS = [
    "OVERDRAFT",
    "INTEREST CHARGE",
    "INTEREST CHARGES",
    "INTEREST ADJUSTMENT",
    "DEPOSIT INTEREST",
]
EXCLUDE_FROM_PAIRING_TOKENS = list({*FEE_KEYWORDS, *NONTRANSFER_TOKENS})


@dataclass
class Txn:
    idx: int
    transaction_id: str
    date: datetime
    amount: float
    currency: str
    account_id: str
    description: str
    source_file: str

    def is_debit(self) -> bool:
        return self.amount < 0

    def is_credit(self) -> bool:
        return self.amount > 0

    @property
    def desc_hash8(self) -> str:
        import hashlib

        return hashlib.sha256(self.description.encode("utf-8")).hexdigest()[:8]

    def has_desc_token(self, tokens: Sequence[str]) -> bool:
        upper = self.description.upper()
        return any(tok in upper for tok in tokens)


@dataclass
class Match:
    debit: Txn
    credit: Txn
    score: float
    method: str
    fee_txn_ids: List[str]


def load_normalized(processed_dir: Path) -> List[Txn]:
    """Load per-account ledger CSVs from processed_dir into Txn list.

    This expects the standardized processed schema columns to be present.
    """
    txns: List[Txn] = []
    files = sorted(processed_dir.glob("*.csv"))
    for f in files:
        try:
            df = pd.read_csv(f)
        except Exception:  # pragma: no cover
            continue
        required = {
            "transaction_id",
            "date",
            "description",
            "amount",
            "currency",
            "account_id",
            "source_file",
        }
        missing = required - set(df.columns)
        if missing:
            continue
        for _i, row in df.iterrows():
            try:
                dt = datetime.strptime(str(row["date"]), "%Y-%m-%d")
                amt = float(row["amount"])
                txns.append(
                    Txn(
                        idx=len(txns),
                        transaction_id=str(row["transaction_id"]),
                        date=dt,
                        amount=amt,
                        currency=str(row["currency"]),
                        account_id=str(row["account_id"]),
                        description=str(row["description"] or ""),
                        source_file=str(row["source_file"]),
                    )
                )
            except Exception:  # pragma: no cover
                continue
    return txns


def _amount_closeness(a: float, b: float, epsilon: float) -> float:
    """Return 1.0 when amounts match within epsilon, else a decaying score.

    When epsilon <= 0, enforce exact absolute-amount equality to avoid fuzzy matches.
    """
    diff = abs(abs(a) - abs(b))
    if epsilon <= 0:
        return 1.0 if diff == 0 else 0.0
    if diff <= epsilon:
        return 1.0
    return max(0.0, 1.0 - (diff - epsilon) / (epsilon * 2.0))


def _date_proximity(a: datetime, b: datetime, window_days: int) -> float:
    d = abs((a - b).days)
    if d == 0:
        return 1.0
    if d > window_days:
        return 0.0
    return max(0.0, 1.0 - (d / max(1.0, float(window_days))))


def _find_nearby_fees(
    debit: Txn, all_txns: Sequence[Txn], fee_max: float, day_window: int
) -> List[Txn]:
    fees: List[Txn] = []
    start = debit.date - timedelta(days=day_window)
    end = debit.date + timedelta(days=day_window)
    for t in all_txns:
        if t.account_id != debit.account_id:
            continue
        if not (start <= t.date <= end):
            continue
        if t.amount >= 0:
            continue
        if abs(t.amount) <= fee_max and t.has_desc_token(FEE_KEYWORDS):
            fees.append(t)
    uniq: Dict[str, Txn] = {
        f.transaction_id: f for f in fees if f.transaction_id != debit.transaction_id
    }
    return list(uniq.values())


def score_pair(debit: Txn, credit: Txn, epsilon: float, window_days: int) -> float:
    amt_score = _amount_closeness(debit.amount, credit.amount, epsilon)
    date_score = _date_proximity(debit.date, credit.date, window_days)
    cue_score = (
        1.0
        if (debit.has_desc_token(DESCRIPTION_TOKENS) or credit.has_desc_token(DESCRIPTION_TOKENS))
        else 0.0
    )
    return 0.6 * amt_score + 0.3 * date_score + 0.1 * cue_score


# ---- Matching helpers (extracted to reduce cognitive complexity) ----


def _is_bank2_biz_loc_pair(a: str, b: str) -> bool:
    s = {a, b}
    return "BANK2_BIZ" in s and "BANK2_LOC" in s


def _valid_sign_pair(d: Txn, o: Txn) -> bool:
    # Normally require opposite signs, but allow same-sign for special bank pair
    if d.amount * o.amount < 0:
        return True
    if _is_bank2_biz_loc_pair(d.account_id, o.account_id):
        return True
    return False


def _filter_candidate_others(
    d: Txn,
    txns_by_ccy: Dict[str, List[Txn]],
    matched_other_ids: set[str],
) -> List[Txn]:
    """Candidates in same currency, different account, not already matched, valid sign, not excluded."""
    return [
        o
        for o in txns_by_ccy.get(d.currency, [])
        if (
            o.account_id != d.account_id
            and o.transaction_id not in matched_other_ids
            and _valid_sign_pair(d, o)
            and not o.has_desc_token(EXCLUDE_FROM_PAIRING_TOKENS)
        )
    ]


def _select_best_match(
    d: Txn,
    candidates: Sequence[Txn],
    *,
    epsilon_direct: float,
    epsilon_interac: float,
    window_days: int,
) -> Optional[Tuple[Txn, float, str]]:
    """Return (credit, score, method) for best candidate using two-phase selection."""
    best: Optional[Tuple[Txn, float, str]] = None
    # Phase 1: same-day direct
    for c in candidates:
        if d.date != c.date:
            continue
        s = score_pair(d, c, epsilon_direct, window_days=0)
        if _is_bank2_biz_loc_pair(d.account_id, c.account_id):
            s = min(1.0, s + 0.05)
        if s >= 0.95 and (not best or s > best[1]):
            best = (c, s, "direct_same_day")
    if best is not None:
        return best
    # Phase 2: window interac
    for c in candidates:
        if abs((d.date - c.date).days) > window_days:
            continue
        s = score_pair(d, c, epsilon_interac, window_days)
        if _is_bank2_biz_loc_pair(d.account_id, c.account_id):
            s = min(1.0, s + 0.05)
        if s >= 0.6 and (not best or s > best[1]):
            best = (c, s, "window_interac")
    return best


def _try_match_for_debit(
    d: Txn,
    *,
    txns_by_ccy: Dict[str, List[Txn]],
    matched_other_ids: set[str],
    all_txns: Sequence[Txn],
    epsilon_direct: float,
    epsilon_interac: float,
    window_days: int,
    fee_max_amount: float,
    fee_day_window: int,
) -> Optional[Match]:
    if d.has_desc_token(EXCLUDE_FROM_PAIRING_TOKENS):
        return None
    cand_others = _filter_candidate_others(d, txns_by_ccy, matched_other_ids)
    if not cand_others:
        return None
    best = _select_best_match(
        d,
        cand_others,
        epsilon_direct=epsilon_direct,
        epsilon_interac=epsilon_interac,
        window_days=window_days,
    )
    if best is None:
        return None
    credit, score, method = best
    fees = _find_nearby_fees(d, all_txns, fee_max_amount, fee_day_window)
    return Match(
        debit=d,
        credit=credit,
        score=score,
        method=method,
        fee_txn_ids=[f.transaction_id for f in fees],
    )


def compute_matches(
    processed_dir: Path,
    window_days: int = 3,
    epsilon_direct: float = 0.0,
    epsilon_interac: float = 0.0,
    fee_max_amount: float = 3.00,
    fee_day_window: int = 1,
) -> List[Match]:
    """Compute likely transfer matches between accounts.

    Delegates candidate filtering, scoring, and fee attachment to small helpers
    to reduce cognitive complexity. Behavior is preserved.
    """
    txns = load_normalized(processed_dir)
    if not txns:
        return []

    debits = [t for t in txns if t.is_debit()]
    _credits = [t for t in txns if t.is_credit()]  # kept for parity; not directly used

    # Group transactions by currency for efficient candidate retrieval
    txns_by_ccy: Dict[str, List[Txn]] = {}
    for t in txns:
        txns_by_ccy.setdefault(t.currency, []).append(t)

    matched_other_ids: set[str] = set()
    matches: List[Match] = []

    debits_sorted = sorted(debits, key=lambda t: (t.date, abs(t.amount)), reverse=True)
    used_debits: set[str] = set()

    for d in debits_sorted:
        if d.transaction_id in used_debits:
            continue
        m = _try_match_for_debit(
            d=d,
            txns_by_ccy=txns_by_ccy,
            matched_other_ids=matched_other_ids,
            all_txns=txns,
            epsilon_direct=epsilon_direct,
            epsilon_interac=epsilon_interac,
            window_days=window_days,
            fee_max_amount=fee_max_amount,
            fee_day_window=fee_day_window,
        )
        if m:
            matches.append(m)
            matched_other_ids.add(m.credit.transaction_id)
            used_debits.add(d.transaction_id)
            if m.credit.is_debit():
                used_debits.add(m.credit.transaction_id)

    return matches


__all__ = [
    "Txn",
    "Match",
    "load_normalized",
    "score_pair",
    "compute_matches",
]
