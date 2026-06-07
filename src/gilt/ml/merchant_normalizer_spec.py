"""Specifications for merchant_normalizer.normalize_merchant."""

from __future__ import annotations

from gilt.ml.merchant_normalizer import normalize_merchant


class DescribeNormalizeMerchant:
    """normalize_merchant() strips noise tokens and returns a canonical lowercase key."""

    def it_should_strip_amazon_store_code_and_city(self):
        # Amazon-style *STORECODE trailing the merchant token plus trailing city
        result = normalize_merchant("AMZN Mktp CA*BC0BQ7RY2 TORONTO")
        assert result == "amzn mktp ca"

    def it_should_leave_amazon_web_services_distinct(self):
        result = normalize_merchant("amazon web services")
        assert result == "amazon web services"

    def it_should_strip_branch_number_at_sign_and_trailing_city(self):
        # "@ 4268" is a branch number; "HALIBURTON" is a city
        result = normalize_merchant("MOBIL@ 4268 GAS STN HALIBURTON")
        assert result == "mobil gas stn"

    def it_should_strip_e_transfer_prefix_and_trailing_ref_code(self):
        result = normalize_merchant("E-TRANSFER SENT HANDI STORAGE LTD GCXRT5")
        assert result == "handi storage ltd"

    def it_should_strip_fx_tail(self):
        result = normalize_merchant("SP HARNEY SONS TEA MILLERTON - 87.86 USD @ 1.416913")
        assert result == "sp harney sons tea"

    def it_should_strip_hash_store_number_and_city(self):
        result = normalize_merchant("TIM HORTONS #104781 CAMBRIDGE")
        assert result == "tim hortons"

    def it_should_normalize_two_variants_to_same_key(self):
        # Both should collapse to the same canonical key
        v1 = normalize_merchant("SAMPLE STORE #101 ANYTOWN")
        v2 = normalize_merchant("SAMPLE STORE #202 OTHERTOWN")
        assert v1 == v2

    def it_should_be_idempotent(self):
        raw = "TIM HORTONS #104781 CAMBRIDGE"
        first = normalize_merchant(raw)
        second = normalize_merchant(first)
        assert first == second

    def it_should_return_empty_string_for_empty_input(self):
        assert normalize_merchant("") == ""

    def it_should_return_empty_string_for_whitespace_only_input(self):
        assert normalize_merchant("   ") == ""

    def it_should_strip_pos_purchase_prefix(self):
        result = normalize_merchant("POS PURCHASE ACME CORP")
        assert result == "acme corp"

    def it_should_strip_point_of_sale_prefix(self):
        result = normalize_merchant("POINT OF SALE SAMPLE STORE")
        assert result == "sample store"

    def it_should_strip_trailing_province_code(self):
        result = normalize_merchant("EXAMPLE UTILITY ON")
        assert result == "example utility"

    def it_should_strip_e_transfer_received_prefix(self):
        result = normalize_merchant("E-TRANSFER RECEIVED ACME CORP")
        assert result == "acme corp"
