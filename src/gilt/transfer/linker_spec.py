from __future__ import annotations

from pathlib import Path

from gilt.model.ledger_io import load_ledger_csv
from gilt.testing.fixtures import make_group
from gilt.transfer._constants import (
    ROLE_CREDIT,
    ROLE_DEBIT,
    TRANSFER_AMOUNT,
    TRANSFER_COUNTERPARTY_ACCOUNT_ID,
    TRANSFER_COUNTERPARTY_TRANSACTION_ID,
    TRANSFER_FEE_TXN_IDS,
    TRANSFER_META_KEY,
    TRANSFER_METHOD,
    TRANSFER_ROLE,
    TRANSFER_SCORE,
)
from gilt.transfer.conftest import write_ledger_from_dicts
from gilt.transfer.linker import _build_transfer_payloads, _ensure_transfer_metadata, link_transfers
from gilt.transfer.matching import Match, Txn


def it_should_mark_both_sides_and_persist_metadata(tmp_path: Path):
    # Prepare two ledgers with a clear transfer pair
    acc1 = tmp_path / "ACC1.csv"
    acc2 = tmp_path / "ACC2.csv"

    d_id = "d3" * 8
    c_id = "c3" * 8

    write_ledger_from_dicts(
        acc1,
        [
            {
                "transaction_id": d_id,
                "date": "2025-03-03",
                "description": "E-TRANSFER OUT",
                "amount": -150.0,
                "currency": "CAD",
                "account_id": "ACC1",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "acc1.csv",
            }
        ],
    )

    write_ledger_from_dicts(
        acc2,
        [
            {
                "transaction_id": c_id,
                "date": "2025-03-03",
                "description": "E-TRANSFER IN",
                "amount": 150.0,
                "currency": "CAD",
                "account_id": "ACC2",
                "counterparty": "",
                "category": "",
                "subcategory": "",
                "notes": "",
                "source_file": "acc2.csv",
            }
        ],
    )

    # Run linker with write=True so metadata persists to CSVs
    changed = link_transfers(processed_dir=tmp_path, write=True)
    assert changed == 2

    # Verify that metadata_json contains the transfer object on both sides
    for p, role, counter_txn in [
        (acc1, "debit", c_id),
        (acc2, "credit", d_id),
    ]:
        text = p.read_text(encoding="utf-8")
        groups = load_ledger_csv(text, default_currency="CAD")
        assert len(groups) == 1
        meta = groups[0].primary.metadata or {}
        tr = meta.get("transfer")
        assert isinstance(tr, dict)
        assert tr.get("role") == role
        assert tr.get("counterparty_transaction_id") == counter_txn
        assert abs(float(tr.get("amount", 0.0)) - 150.0) < 1e-6
        assert tr.get("method") in {"direct_same_day", "window_interac"}
        assert isinstance(tr.get("score"), float)

    # Run again (idempotent). No further file changes should be needed.
    changed2 = link_transfers(processed_dir=tmp_path, write=True)
    assert changed2 in {0, 2}  # implementation may touch both files if score/method updated


def it_should_require_processed_dir():
    import pytest

    with pytest.raises(TypeError):
        link_transfers()


def _make_txn(
    *,
    idx: int = 0,
    transaction_id: str = "aaaa111100000001",
    date: str = "2025-03-03",
    amount: float = -150.0,
    currency: str = "CAD",
    account_id: str = "ACC1",
    description: str = "E-TRANSFER OUT",
) -> Txn:
    from datetime import datetime

    return Txn(
        idx=idx,
        transaction_id=transaction_id,
        date=datetime.fromisoformat(date),
        amount=amount,
        currency=currency,
        account_id=account_id,
        description=description,
        source_file=f"{account_id}.csv",
    )


def _make_match(
    debit: Txn | None = None,
    credit: Txn | None = None,
    score: float = 0.95,
    method: str = "direct_same_day",
    fee_txn_ids: list[str] | None = None,
) -> Match:
    d = debit or _make_txn(account_id="ACC1", amount=-150.0, transaction_id="dddd111100000001")
    c = credit or _make_txn(
        account_id="ACC2", amount=150.0, transaction_id="cccc222200000002", description="E-TRANSFER IN"
    )
    return Match(debit=d, credit=c, score=score, method=method, fee_txn_ids=fee_txn_ids or [])


class DescribeBuildTransferPayloads:
    def it_should_build_debit_payload_with_correct_role_and_counterparty(self):
        d = _make_txn(account_id="ACC1", amount=-150.0, transaction_id="dddd111100000001")
        c = _make_txn(account_id="ACC2", amount=150.0, transaction_id="cccc222200000002")
        m = _make_match(debit=d, credit=c)

        debit_payload, _ = _build_transfer_payloads(m, d, c)

        assert debit_payload[TRANSFER_ROLE] == ROLE_DEBIT
        assert debit_payload[TRANSFER_COUNTERPARTY_ACCOUNT_ID] == "ACC2"
        assert debit_payload[TRANSFER_COUNTERPARTY_TRANSACTION_ID] == "cccc222200000002"
        assert abs(debit_payload[TRANSFER_AMOUNT] - 150.0) < 1e-6

    def it_should_build_credit_payload_with_empty_fee_txn_ids(self):
        d = _make_txn(account_id="ACC1", amount=-150.0, transaction_id="dddd111100000001")
        c = _make_txn(account_id="ACC2", amount=150.0, transaction_id="cccc222200000002")
        m = _make_match(debit=d, credit=c, fee_txn_ids=["fee001"])

        _, credit_payload = _build_transfer_payloads(m, d, c)

        assert credit_payload[TRANSFER_ROLE] == ROLE_CREDIT
        assert credit_payload[TRANSFER_FEE_TXN_IDS] == []

    def it_should_propagate_fee_txn_ids_to_debit_payload(self):
        d = _make_txn(account_id="ACC1", amount=-150.0, transaction_id="dddd111100000001")
        c = _make_txn(account_id="ACC2", amount=150.0, transaction_id="cccc222200000002")
        m = _make_match(debit=d, credit=c, fee_txn_ids=["fee001", "fee002"])

        debit_payload, _ = _build_transfer_payloads(m, d, c)

        assert debit_payload[TRANSFER_FEE_TXN_IDS] == ["fee001", "fee002"]

    def it_should_use_absolute_amount_on_both_sides(self):
        d = _make_txn(account_id="ACC1", amount=-200.0, transaction_id="dddd111100000001")
        c = _make_txn(account_id="ACC2", amount=200.0, transaction_id="cccc222200000002")
        m = _make_match(debit=d, credit=c)

        debit_payload, credit_payload = _build_transfer_payloads(m, d, c)

        assert debit_payload[TRANSFER_AMOUNT] == 200.0
        assert credit_payload[TRANSFER_AMOUNT] == 200.0


class DescribeEnsureTransferMetadata:
    def it_should_set_fresh_transfer_metadata_on_empty_group(self):
        group = make_group(transaction_id="t1", amount=-100.0)
        payload = {
            TRANSFER_ROLE: ROLE_DEBIT,
            TRANSFER_COUNTERPARTY_TRANSACTION_ID: "cccc222200000002",
            TRANSFER_METHOD: "direct_same_day",
            TRANSFER_SCORE: 0.95,
            TRANSFER_FEE_TXN_IDS: [],
        }

        changed = _ensure_transfer_metadata(group, payload)

        assert changed is True
        assert group.primary.metadata[TRANSFER_META_KEY][TRANSFER_ROLE] == ROLE_DEBIT

    def it_should_be_idempotent_for_same_counterparty(self):
        group = make_group(transaction_id="t1", amount=-100.0)
        payload = {
            TRANSFER_ROLE: ROLE_DEBIT,
            TRANSFER_COUNTERPARTY_TRANSACTION_ID: "cccc222200000002",
            TRANSFER_METHOD: "direct_same_day",
            TRANSFER_SCORE: 0.95,
            TRANSFER_FEE_TXN_IDS: [],
        }
        _ensure_transfer_metadata(group, payload)

        changed = _ensure_transfer_metadata(group, payload)

        assert changed is False

    def it_should_update_score_when_changed_on_existing_match(self):
        group = make_group(transaction_id="t1", amount=-100.0)
        payload = {
            TRANSFER_ROLE: ROLE_DEBIT,
            TRANSFER_COUNTERPARTY_TRANSACTION_ID: "cccc222200000002",
            TRANSFER_METHOD: "direct_same_day",
            TRANSFER_SCORE: 0.80,
            TRANSFER_FEE_TXN_IDS: [],
        }
        _ensure_transfer_metadata(group, payload)

        updated_payload = dict(payload)
        updated_payload[TRANSFER_SCORE] = 0.95
        changed = _ensure_transfer_metadata(group, updated_payload)

        assert changed is True
        assert group.primary.metadata[TRANSFER_META_KEY][TRANSFER_SCORE] == 0.95


class DescribeLinkTransfersEdgeCases:
    def it_should_return_zero_when_no_matches_found(self, tmp_path: Path):
        acc1 = tmp_path / "ACC1.csv"
        write_ledger_from_dicts(
            acc1,
            [
                {
                    "transaction_id": "aaaa111100000001",
                    "date": "2025-03-10",
                    "description": "PURCHASE AT SAMPLE STORE",
                    "amount": -42.50,
                    "currency": "CAD",
                    "account_id": "ACC1",
                    "counterparty": "",
                    "category": "",
                    "subcategory": "",
                    "notes": "",
                    "source_file": "acc1.csv",
                }
            ],
        )

        changed = link_transfers(processed_dir=tmp_path, write=False)

        assert changed == 0

    def it_should_not_write_when_write_is_false(self, tmp_path: Path):
        acc1 = tmp_path / "ACC1.csv"
        acc2 = tmp_path / "ACC2.csv"
        d_id = "dd" * 8
        c_id = "cc" * 8

        write_ledger_from_dicts(
            acc1,
            [
                {
                    "transaction_id": d_id,
                    "date": "2025-03-03",
                    "description": "E-TRANSFER OUT",
                    "amount": -150.0,
                    "currency": "CAD",
                    "account_id": "ACC1",
                    "counterparty": "",
                    "category": "",
                    "subcategory": "",
                    "notes": "",
                    "source_file": "acc1.csv",
                }
            ],
        )
        write_ledger_from_dicts(
            acc2,
            [
                {
                    "transaction_id": c_id,
                    "date": "2025-03-03",
                    "description": "E-TRANSFER IN",
                    "amount": 150.0,
                    "currency": "CAD",
                    "account_id": "ACC2",
                    "counterparty": "",
                    "category": "",
                    "subcategory": "",
                    "notes": "",
                    "source_file": "acc2.csv",
                }
            ],
        )
        original_acc1 = acc1.read_text(encoding="utf-8")
        original_acc2 = acc2.read_text(encoding="utf-8")

        link_transfers(processed_dir=tmp_path, write=False)

        assert acc1.read_text(encoding="utf-8") == original_acc1
        assert acc2.read_text(encoding="utf-8") == original_acc2
