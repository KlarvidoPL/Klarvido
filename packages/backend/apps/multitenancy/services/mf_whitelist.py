"""
Company lookup in the Polish Ministry of Finance "White List" of VAT taxpayers (Wykaz podatników VAT).

API docs: https://wl-api.mf.gov.pl - `GET /api/search/nip/{nip}?date=YYYY-MM-DD` returns
`{"result": {"subject": {...} | null, ...}}`. Used only to prefill organization company details, so every
failure (company not listed, API down, timeout, malformed response) degrades to "nothing found" and the user
fills the fields in by hand - it never blocks creating an organization.
"""

import logging
from dataclasses import dataclass
from typing import Optional

import requests
from django.conf import settings
from django.utils import timezone

from ..constants import VatStatus

logger = logging.getLogger(__name__)

MF_VAT_STATUS_MAP = {
    "czynny": VatStatus.ACTIVE,
    "zwolniony": VatStatus.EXEMPT,
    "niezarejestrowany": VatStatus.NOT_REGISTERED,
}


@dataclass(frozen=True)
class CompanyDetails:
    company_name: str
    regon: str
    address: str
    vat_status: str


def lookup_company_by_nip(nip: str) -> Optional[CompanyDetails]:
    """Return the company registered under `nip` (already validated/normalized), or None if not found/unavailable."""
    url = f"{settings.MF_WHITELIST_API_URL.rstrip('/')}/api/search/nip/{nip}"
    try:
        response = requests.get(
            url,
            params={"date": timezone.localdate().isoformat()},
            timeout=settings.MF_WHITELIST_API_TIMEOUT,
        )
        response.raise_for_status()
        subject = (response.json().get("result") or {}).get("subject")
    except (requests.RequestException, ValueError, AttributeError) as e:
        logger.warning("MF White List lookup failed for NIP %s: %s: %s", nip, type(e).__name__, e)
        return None

    if not subject:
        return None

    status = (subject.get("statusVat") or "").strip().lower()
    return CompanyDetails(
        company_name=(subject.get("name") or "").strip(),
        regon=(subject.get("regon") or "").strip(),
        address=(subject.get("workingAddress") or subject.get("residenceAddress") or "").strip(),
        vat_status=MF_VAT_STATUS_MAP.get(status, VatStatus.NOT_REGISTERED if status else ""),
    )
