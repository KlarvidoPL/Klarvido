from unittest.mock import MagicMock, patch

import pytest
import requests

from ..constants import VatStatus
from ..services.mf_whitelist import CompanyDetails, lookup_company_by_nip

pytestmark = pytest.mark.django_db

MF_SUBJECT = {
    "name": "ACME SPÓŁKA Z OGRANICZONĄ ODPOWIEDZIALNOŚCIĄ",
    "nip": "9721382373",
    "statusVat": "Czynny",
    "regon": "123456785",
    "residenceAddress": None,
    "workingAddress": "UL. PRZYKŁADOWA 1, 00-001 WARSZAWA",
}


def mf_response(payload, status_code=200):
    response = MagicMock()
    response.status_code = status_code
    response.json.return_value = payload
    if status_code >= 400:
        response.raise_for_status.side_effect = requests.HTTPError(f"{status_code}")
    return response


@patch("apps.multitenancy.services.mf_whitelist.requests.get")
class TestLookupCompanyByNip:
    def test_found(self, mock_get):
        mock_get.return_value = mf_response({"result": {"subject": MF_SUBJECT}})

        assert lookup_company_by_nip("9721382373") == CompanyDetails(
            company_name=MF_SUBJECT["name"],
            regon="123456785",
            address="UL. PRZYKŁADOWA 1, 00-001 WARSZAWA",
            vat_status=VatStatus.ACTIVE,
        )
        url = mock_get.call_args.args[0]
        assert url.endswith("/api/search/nip/9721382373")
        assert "date" in mock_get.call_args.kwargs["params"]

    def test_falls_back_to_residence_address(self, mock_get):
        subject = {**MF_SUBJECT, "workingAddress": None, "residenceAddress": "UL. DOMOWA 2, 30-001 KRAKÓW"}
        mock_get.return_value = mf_response({"result": {"subject": subject}})

        assert lookup_company_by_nip("9721382373").address == "UL. DOMOWA 2, 30-001 KRAKÓW"

    @pytest.mark.parametrize(
        "status_vat, expected",
        [
            ("Czynny", VatStatus.ACTIVE),
            ("Zwolniony", VatStatus.EXEMPT),
            ("Niezarejestrowany", VatStatus.NOT_REGISTERED),
        ],
    )
    def test_vat_status_mapping(self, mock_get, status_vat, expected):
        mock_get.return_value = mf_response({"result": {"subject": {**MF_SUBJECT, "statusVat": status_vat}}})

        assert lookup_company_by_nip("9721382373").vat_status == expected

    def test_not_found(self, mock_get):
        mock_get.return_value = mf_response({"result": {"subject": None, "requestId": "abc"}})

        assert lookup_company_by_nip("9721382373") is None

    def test_http_error(self, mock_get):
        mock_get.return_value = mf_response({"code": "WL-113", "message": "error"}, status_code=400)

        assert lookup_company_by_nip("9721382373") is None

    def test_timeout(self, mock_get):
        mock_get.side_effect = requests.Timeout()

        assert lookup_company_by_nip("9721382373") is None

    def test_malformed_json(self, mock_get):
        response = mf_response(None)
        response.json.side_effect = ValueError("not json")
        mock_get.return_value = response

        assert lookup_company_by_nip("9721382373") is None
