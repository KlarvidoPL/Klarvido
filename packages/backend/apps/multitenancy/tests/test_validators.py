import pytest
from rest_framework import serializers

from ..validators import is_valid_nip, is_valid_regon, normalize_tax_id, validate_nip, validate_regon, validate_tax_id

pytestmark = pytest.mark.django_db


class TestNipValidation:
    @pytest.mark.parametrize("nip", ["9721382373", "1234563218", "972-138-23-73", "972 138 23 73"])
    def test_valid_nip(self, nip):
        assert is_valid_nip(nip)

    @pytest.mark.parametrize(
        "nip",
        [
            "",
            "123",
            "97213823730",  # too long
            "9721382374",  # wrong check digit
            "1234567890",  # checksum mod 11 == 10, never valid
            "97213823a3",
        ],
    )
    def test_invalid_nip(self, nip):
        assert not is_valid_nip(nip)

    def test_validate_nip_returns_normalized_value(self):
        assert validate_nip("972-138-23-73") == "9721382373"

    def test_validate_nip_raises(self):
        with pytest.raises(serializers.ValidationError):
            validate_nip("9721382374")


class TestRegonValidation:
    @pytest.mark.parametrize("regon", ["123456785", "12345678512347"])
    def test_valid_regon(self, regon):
        assert is_valid_regon(regon)

    @pytest.mark.parametrize("regon", ["123456789", "12345678512348", "12345", "abcdefghi"])
    def test_invalid_regon(self, regon):
        assert not is_valid_regon(regon)

    def test_validate_regon_allows_empty(self):
        assert validate_regon("") == ""

    def test_validate_regon_raises(self):
        with pytest.raises(serializers.ValidationError):
            validate_regon("123456789")


class TestTaxIdValidation:
    @pytest.mark.parametrize("value", ["9721382373", "PL9721382373", "pl 972-138-23-73", "PL-972-138-23-73"])
    def test_polish_tax_id_with_or_without_country_prefix(self, value):
        assert normalize_tax_id(value, "PL") == "9721382373"
        assert validate_tax_id(value, "PL") == "9721382373"

    def test_invalid_polish_tax_id(self):
        with pytest.raises(serializers.ValidationError) as e:
            validate_tax_id("PL9721382374", "PL")
        assert e.value.detail[0].code == "invalid_nip"

    def test_unsupported_country(self):
        with pytest.raises(serializers.ValidationError) as e:
            validate_tax_id("123456789", "DE")
        assert e.value.detail[0].code == "unsupported_country"
