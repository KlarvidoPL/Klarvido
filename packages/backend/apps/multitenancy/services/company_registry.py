"""
Company registries per country, used to prefill organization details from a tax ID.

Each entry takes an already validated/normalized tax ID and returns `CompanyDetails` or None (not found or registry
unavailable - callers leave the fields for the user). A supported country without a registry simply gets no prefill.
"""

from typing import Callable, Optional

from ..constants import CompanyCountry
from .mf_whitelist import CompanyDetails, lookup_company_by_nip

COMPANY_REGISTRIES: dict[str, Callable[[str], Optional[CompanyDetails]]] = {
    CompanyCountry.POLAND: lookup_company_by_nip,
}


def lookup_company(country: str, tax_id: str) -> Optional[CompanyDetails]:
    lookup = COMPANY_REGISTRIES.get(country)
    return lookup(tax_id) if lookup else None
