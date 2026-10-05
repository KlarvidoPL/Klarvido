"""
Business rules for the organization's KSeF token: eligibility, live verification, encrypted storage and audit logging.

The schema layer only calls these functions and maps the returned error codes; it never touches the ciphertext.
"""

import logging
from dataclasses import dataclass
from typing import Optional

from django.utils import timezone

from apps.multitenancy.constants import ActionType, CompanyCountry
from apps.sso.constants import SSOAuditEventType
from apps.sso.models import SSOAuditLog
from common.action_logging.service import log_action

from . import crypto
from .client import verify_token
from .constants import MAX_TOKEN_LENGTH, KsefCredentialStatus, KsefErrorCode
from .models import KsefCredential

logger = logging.getLogger(__name__)

ENTITY_TYPE = "ksef_credential"


@dataclass(frozen=True)
class CredentialResult:
    credential: Optional[KsefCredential]
    error_code: str = ""


def _eligibility_error(tenant) -> Optional[str]:
    if tenant.country != CompanyCountry.POLAND:
        return KsefErrorCode.COUNTRY_NOT_SUPPORTED
    if not tenant.nip:
        return KsefErrorCode.NIP_MISSING
    return None


def get_credential(tenant) -> Optional[KsefCredential]:
    return KsefCredential.objects.filter(tenant=tenant).first()


def _log(tenant, user, action_type: str, credential: Optional[KsefCredential], metadata: dict) -> None:
    log_action(
        tenant_id=tenant.pk,
        action_type=action_type,
        entity_type=ENTITY_TYPE,
        entity_id=str(tenant.pk),
        entity_name="KSeF token",
        actor_user=user,
        metadata=metadata,
    )


def _log_security_event(tenant, user, event_type: str, description: str, metadata: dict, error_code: str = "") -> None:
    """Record the change in the organization's Security audit log. Never pass the token itself in metadata."""
    SSOAuditLog.log_event(
        event_type=event_type,
        tenant=tenant,
        user=user,
        description=description,
        metadata=metadata,
        success=not error_code,
        error_message=error_code,
    )


def save_token(tenant, user, token: str) -> CredentialResult:
    """Verify the token with KSeF and, unless KSeF rejected it, store it encrypted (replacing any previous token)."""
    error = _eligibility_error(tenant)
    if error:
        return CredentialResult(None, error)

    token = (token or "").strip()
    if not token or len(token) > MAX_TOKEN_LENGTH:
        return CredentialResult(None, KsefErrorCode.TOKEN_EMPTY)

    try:
        crypto.ensure_encryption_configured()
    except crypto.KsefEncryptionNotConfigured:
        logger.error("KSEF_ENCRYPTION_KEYS is not configured; refusing to store a KSeF token")
        return CredentialResult(None, KsefErrorCode.ENCRYPTION_NOT_CONFIGURED)

    check = verify_token(tenant.nip, token)
    if check.status == KsefCredentialStatus.INVALID:
        return CredentialResult(None, check.error_code)

    payload = crypto.encrypt_token(tenant.pk, token)
    credential, created = KsefCredential.objects.update_or_create(
        tenant=tenant,
        defaults={
            "encrypted_token": payload,
            "token_hint": token[-4:],
            "token_name": check.token_name,
            "status": check.status,
            "last_verified_at": timezone.now() if check.status == KsefCredentialStatus.VALID else None,
            "last_error_code": check.error_code,
            "updated_by": user,
        },
    )
    _log(
        tenant,
        user,
        ActionType.CREATE if created else ActionType.UPDATE,
        credential,
        {"operation": "set", "status": credential.status, "token_hint": credential.token_hint},
    )
    _log_security_event(
        tenant,
        user,
        SSOAuditEventType.KSEF_TOKEN_SAVED,
        "KSeF token saved",
        {
            "created": created,
            "status": credential.status,
            "token_hint": credential.token_hint,
            "token_name": credential.token_name,
        },
        check.error_code if check.status != KsefCredentialStatus.VALID else "",
    )
    return CredentialResult(credential, check.error_code)


def retest_token(tenant, user) -> CredentialResult:
    """Decrypt the stored token and check it with KSeF again."""
    credential = get_credential(tenant)
    if credential is None:
        return CredentialResult(None, KsefErrorCode.NOT_CONFIGURED)

    try:
        crypto.ensure_encryption_configured()
        token = crypto.decrypt_token(tenant.pk, credential.encrypted_token)
    except (crypto.KsefEncryptionNotConfigured, crypto.KsefDecryptionError):
        logger.error("Stored KSeF token for tenant %s could not be decrypted", tenant.pk)
        return CredentialResult(credential, KsefErrorCode.DECRYPTION_FAILED)

    check = verify_token(tenant.nip, token)
    credential.status = check.status
    credential.last_error_code = check.error_code
    if check.status == KsefCredentialStatus.VALID:
        credential.last_verified_at = timezone.now()
    if check.token_name:
        credential.token_name = check.token_name
    # Re-encrypting with the newest key is how a key rotation reaches stored tokens.
    credential.encrypted_token = crypto.encrypt_token(tenant.pk, token)
    credential.updated_by = user
    credential.save(
        update_fields=[
            "encrypted_token",
            "status",
            "last_error_code",
            "last_verified_at",
            "token_name",
            "updated_by",
            "updated_at",
        ]
    )

    _log(
        tenant,
        user,
        ActionType.UPDATE,
        credential,
        {"operation": "test", "status": credential.status, "token_hint": credential.token_hint},
    )
    _log_security_event(
        tenant,
        user,
        SSOAuditEventType.KSEF_TOKEN_TESTED,
        "KSeF token checked",
        {"status": credential.status, "token_hint": credential.token_hint, "token_name": credential.token_name},
        check.error_code if check.status != KsefCredentialStatus.VALID else "",
    )
    return CredentialResult(credential, check.error_code)


def delete_token(tenant, user) -> bool:
    credential = get_credential(tenant)
    if credential is None:
        return False
    hint = credential.token_hint
    name = credential.token_name
    credential.delete()
    _log(tenant, user, ActionType.DELETE, None, {"operation": "delete", "token_hint": hint})
    _log_security_event(
        tenant,
        user,
        SSOAuditEventType.KSEF_TOKEN_DELETED,
        "KSeF token removed",
        {"token_hint": hint, "token_name": name},
    )
    return True
