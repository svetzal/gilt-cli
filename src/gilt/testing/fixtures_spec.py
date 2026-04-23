from __future__ import annotations

from datetime import date

from gilt.testing.fixtures import make_group, make_match, make_transaction


class DescribeFixtures:
    def it_should_create_default_transaction(self):
        txn = make_transaction()
        assert txn.transaction_id == "aabbccdd11223344"
        assert txn.date == date(2025, 3, 10)
        assert txn.description == "SAMPLE STORE ANYTOWN"
        assert txn.amount == -42.50
        assert txn.currency == "CAD"
        assert txn.account_id == "MYBANK_CHQ"

    def it_should_override_transaction_fields(self):
        txn = make_transaction(amount=-100.00, description="CUSTOM STORE")
        assert txn.amount == -100.00
        assert txn.description == "CUSTOM STORE"
        assert txn.transaction_id == "aabbccdd11223344"

    def it_should_create_default_group(self):
        group = make_group()
        assert group.primary.transaction_id == "aabbccdd11223344"
        assert group.group_id == "aabbccdd11223344"
        assert group.splits == []
        assert group.tolerance == 0.01

    def it_should_build_group_from_transaction_kwargs(self):
        group = make_group(description="CUSTOM TXN")
        assert group.primary.description == "CUSTOM TXN"
        assert group.group_id == group.primary.transaction_id

    def it_should_accept_prebuilt_primary_transaction(self):
        txn = make_transaction(amount=-50.00)
        group = make_group(primary=txn)
        assert group.primary.amount == -50.00
        assert group.primary is txn

    def it_should_accept_group_specific_kwargs(self):
        txn = make_transaction()
        group = make_group(primary=txn, group_id="custom-group-id", tolerance=0.05)
        assert group.group_id == "custom-group-id"
        assert group.tolerance == 0.05

    def it_should_create_default_match(self):
        match = make_match()
        assert match.pair.txn1_id == "aaaa111100000001"
        assert match.pair.txn1_amount == -200.00
        assert match.pair.txn2_id == "bbbb222200000002"
        assert match.pair.txn2_amount == -200.00
        assert match.assessment.is_duplicate is True
        assert match.assessment.confidence == 0.88

    def it_should_override_match_pair_fields(self):
        match = make_match(txn1_amount=-150.00, txn1_description="CUSTOM CORP")
        assert match.pair.txn1_amount == -150.00
        assert match.pair.txn1_description == "CUSTOM CORP"
        assert match.pair.txn2_amount == -200.00

    def it_should_override_match_assessment_fields(self):
        match = make_match(is_duplicate=False, confidence=0.45, reasoning="Different amounts")
        assert match.assessment.is_duplicate is False
        assert match.assessment.confidence == 0.45
        assert match.assessment.reasoning == "Different amounts"
