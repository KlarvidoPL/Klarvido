import pytest
from rest_framework import serializers

from ..validators import is_valid_nip, is_valid_regon, validate_nip, validate_regon

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
