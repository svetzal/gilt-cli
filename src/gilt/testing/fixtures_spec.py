from __future__ import annotations

from datetime import date

from gilt.model.category import Category
from gilt.testing.fixtures import (
    make_category_config,
    make_group,
    make_match,
    make_pair,
    make_transaction,
)


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

    def it_should_create_default_pair(self):
        pair = make_pair()
        assert pair.txn1_id == "aaaa111100000001"
        assert pair.txn1_date == date(2025, 4, 10)
        assert pair.txn1_description == "ACME CORP PAYMENT"
        assert pair.txn1_amount == -200.00
        assert pair.txn1_account == "MYBANK_CHQ"
        assert pair.txn2_id == "bbbb222200000002"
        assert pair.txn2_description == "ACME CORP PMT"
        assert pair.txn1_source_file is None
        assert pair.txn2_source_file is None

    def it_should_override_pair_fields(self):
        pair = make_pair(txn1_id="custom001", txn1_amount=-50.00, txn2_description="CUSTOM DESC")
        assert pair.txn1_id == "custom001"
        assert pair.txn1_amount == -50.00
        assert pair.txn2_description == "CUSTOM DESC"
        assert pair.txn2_id == "bbbb222200000002"

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


class DescribeMakeCategoryConfig:
    def it_should_create_default_category_config(self):
        config = make_category_config()
        assert len(config.categories) == 3
        housing = config.find_category("Housing")
        assert housing is not None
        assert len(housing.subcategories) == 2
        assert housing.budget is not None
        assert housing.budget.amount == 2000.0
        from gilt.model.category import BudgetPeriod

        assert housing.budget.period == BudgetPeriod.monthly
        groceries = config.find_category("Groceries")
        assert groceries is not None
        assert groceries.budget is not None
        assert groceries.budget.amount == 500.0
        assert groceries.budget.period == BudgetPeriod.monthly
        transportation = config.find_category("Transportation")
        assert transportation is not None
        assert transportation.budget is None

    def it_should_override_categories_list(self):
        config = make_category_config(categories=[Category(name="Custom")])
        assert len(config.categories) == 1
        assert config.categories[0].name == "Custom"
