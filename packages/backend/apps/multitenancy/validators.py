import re

from django.utils.translation import gettext_lazy as _
from rest_framework import serializers

from .constants import CompanyCountry

NIP_WEIGHTS = (6, 5, 7, 2, 3, 4, 5, 6, 7)
REGON_9_WEIGHTS = (8, 9, 2, 3, 4, 5, 6, 7)
REGON_14_WEIGHTS = (2, 4, 8, 5, 0, 9, 7, 3, 6, 1, 2, 4, 8)


def normalize_digits(value: str) -> str:
    """Strip the separators people commonly type into NIP/REGON numbers (spaces, dashes)."""
    return re.sub(r"[\s-]", "", value or "")


def is_valid_nip(value: str) -> bool:
    nip = normalize_digits(value)
    if not re.fullmatch(r"\d{10}", nip):
        return False
    checksum = sum(int(digit) * weight for digit, weight in zip(nip[:9], NIP_WEIGHTS, strict=True)) % 11
    return checksum != 10 and checksum == int(nip[9])


def _regon_checksum_matches(regon: str, weights: tuple) -> bool:
    checksum = sum(int(digit) * weight for digit, weight in zip(regon[: len(weights)], weights, strict=True)) % 11
    return (0 if checksum == 10 else checksum) == int(regon[len(weights)])


def is_valid_regon(value: str) -> bool:
    regon = normalize_digits(value)
    if re.fullmatch(r"\d{9}", regon):
        return _regon_checksum_matches(regon, REGON_9_WEIGHTS)
    if re.fullmatch(r"\d{14}", regon):
        return _regon_checksum_matches(regon, REGON_14_WEIGHTS)
    return False


def normalize_tax_id(value: str, country: str) -> str:
    """
    Strips separators and an optional leading country code - people often paste the EU VAT number form, which for
    Poland is just "PL" + NIP (e.g. "PL 972-138-23-73").
    """
    tax_id = normalize_digits(value)
    if country and tax_id[: len(country)].upper() == country.upper():
        tax_id = tax_id[len(country) :]
    return tax_id


# The national part of the tax ID differs per country (length, format, checksum) - only the "country prefix + national
# number" shape of EU VAT numbers is shared - so each supported country brings its own check.
TAX_ID_VALIDATORS = {
    CompanyCountry.POLAND: is_valid_nip,
}


def validate_tax_id(value: str, country: str) -> str:
    """DRF-style validator: returns the normalized tax ID (no country prefix) or raises ValidationError."""
    is_valid = TAX_ID_VALIDATORS.get(country)
    if is_valid is None:
        raise serializers.ValidationError(_("Unsupported country"), code="unsupported_country")
    tax_id = normalize_tax_id(value, country)
    if not is_valid(tax_id):
        raise serializers.ValidationError(_("Invalid NIP number"), code="invalid_nip")
    return tax_id


def validate_nip(value: str) -> str:
    """DRF-style validator: returns the normalized NIP or raises ValidationError."""
    nip = normalize_digits(value)
    if not is_valid_nip(nip):
        raise serializers.ValidationError(_("Invalid NIP number"), code="invalid_nip")
    return nip


def validate_regon(value: str) -> str:
    """DRF-style validator: returns the normalized REGON (empty allowed) or raises ValidationError."""
    regon = normalize_digits(value)
    if regon and not is_valid_regon(regon):
        raise serializers.ValidationError(_("Invalid REGON number"), code="invalid_regon")
    return regon
