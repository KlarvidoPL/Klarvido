"""
WebAuthn/Passkeys implementation for passwordless authentication.
Provides registration and authentication flows for passkeys.

Security Features:
- Proper cryptographic signature verification using COSE keys
- Origin validation (always enforced, explicit override for development)
- Sign count verification with strict enforcement option
- Challenge replay protection
"""

import base64
import hashlib
import json
import logging
import secrets
from typing import Dict, Any, Tuple, List
from urllib.parse import urlparse

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.backends import default_backend
from cryptography.exceptions import InvalidSignature

from django.conf import settings
from django.db import IntegrityError, transaction
from webauthn import verify_registration_response
from webauthn.helpers import base64url_to_bytes, bytes_to_base64url, parse_authenticator_data, parse_backup_flags
from webauthn.helpers.cose import COSEAlgorithmIdentifier

from apps.users.models import User
from apps.sso.models import UserPasskey, WebAuthnChallenge, SSOAuditLog
from apps.sso.constants import SSOAuditEventType

logger = logging.getLogger(__name__)


# COSE algorithm identifiers
COSE_ALG_ES256 = -7  # ECDSA with SHA-256
COSE_ALG_RS256 = -257  # RSASSA-PKCS1-v1_5 with SHA-256

# COSE key types
COSE_KTY_EC2 = 2  # Elliptic Curve
COSE_KTY_RSA = 3  # RSA


class WebAuthnService:
    """
    WebAuthn Relying Party implementation.
    Handles passkey registration and authentication.

    Security Configuration (settings.py):
    - WEBAUTHN_ALLOW_ORIGIN_MISMATCH: Allow origin mismatch for local development (default: False)
    - WEBAUTHN_STRICT_SIGN_COUNT: Reject sign-count anomalies when enabled (default: False).
      Synced passkeys may use zero counters.
    """

    # Challenge TTL in seconds
    CHALLENGE_TTL = 300  # 5 minutes

    def __init__(self, user: User = None):
        """
        Initialize WebAuthn service.

        Args:
            user: The user for passkey operations (optional for discovery)
        """
        self.user = user
        self.rp_id = self._get_rp_id()
        self.rp_name = getattr(settings, "PROJECT_NAME", "Klarvido")

    def _get_rp_id(self) -> str:
        """Get the Relying Party ID (domain)."""
        # Use the web app URL to determine the RP ID
        web_app_url = getattr(settings, "WEB_APP_URL", "http://localhost:3000")
        parsed = urlparse(web_app_url)
        return parsed.hostname or "localhost"

    def _get_origin(self) -> str:
        """Get the expected origin for WebAuthn."""
        return getattr(settings, "WEB_APP_URL", "http://localhost:3000")

    def _get_allowed_origins(self) -> List[str]:
        """Get list of allowed origins for WebAuthn."""
        origins = [self._get_origin()]
        # Add any additional allowed origins from settings
        extra_origins = getattr(settings, "WEBAUTHN_ALLOWED_ORIGINS", [])
        origins.extend(extra_origins)
        return origins

    def _verify_origin(self, actual_origin: str) -> bool:
        """
        Verify the origin from client data.

        SECURITY: This is always enforced unless explicitly overridden via
        WEBAUTHN_ALLOW_ORIGIN_MISMATCH setting (should NEVER be True in production).

        Args:
            actual_origin: The origin from client data JSON

        Returns:
            True if origin is valid

        Raises:
            ValueError: If origin verification fails
        """
        allowed_origins = self._get_allowed_origins()

        if actual_origin in allowed_origins:
            return True

        # Check for explicit development override (NOT based on DEBUG setting)
        allow_mismatch = getattr(settings, "WEBAUTHN_ALLOW_ORIGIN_MISMATCH", False)

        if allow_mismatch and settings.DEBUG and getattr(settings, "ENVIRONMENT_NAME", "") == "local":
            logger.warning("WebAuthn development origin override used")
            return True

        logger.warning("WebAuthn origin rejected")
        raise ValueError("Origin verification failed")

    def _parse_cose_key(self, cose_key_bytes: bytes) -> Dict[str, Any]:
        """
        Parse a COSE key into its components.

        Args:
            cose_key_bytes: Raw COSE key bytes

        Returns:
            Dict with key components (kty, alg, crv, x, y for EC; n, e for RSA)
        """
        import cbor2

        try:
            cose_key = cbor2.loads(cose_key_bytes)
        except Exception as e:
            raise ValueError(f"Failed to parse COSE key: {e}")

        return cose_key

    def _verify_signature_ec(
        self,
        public_key_bytes: bytes,
        signature: bytes,
        data: bytes,
        algorithm: int,
    ) -> bool:
        """
        Verify an ECDSA signature.

        Args:
            public_key_bytes: Raw EC public key bytes (COSE format)
            signature: The signature to verify (raw r||s format)
            data: The signed data
            algorithm: COSE algorithm identifier

        Returns:
            True if signature is valid

        Raises:
            ValueError: If verification fails
        """
        try:
            cose_key = self._parse_cose_key(public_key_bytes)

            # Extract EC key components
            # COSE key parameter labels: -2 = x, -3 = y
            x = cose_key.get(-2)
            y = cose_key.get(-3)

            if not x or not y:
                raise ValueError("Missing EC key coordinates")

            # Build the public key from x, y coordinates
            # For P-256 curve (ES256)
            from cryptography.hazmat.primitives.asymmetric.ec import (
                EllipticCurvePublicNumbers,
                SECP256R1,
            )

            x_int = int.from_bytes(x, "big")
            y_int = int.from_bytes(y, "big")

            public_numbers = EllipticCurvePublicNumbers(x_int, y_int, SECP256R1())
            public_key = public_numbers.public_key(default_backend())

            # WebAuthn signature is in raw r||s format, need to convert to DER
            if len(signature) == 64:
                r = int.from_bytes(signature[:32], "big")
                s = int.from_bytes(signature[32:], "big")

                # Convert to DER format
                from cryptography.hazmat.primitives.asymmetric.utils import encode_dss_signature

                der_signature = encode_dss_signature(r, s)
            else:
                # Assume it's already DER encoded
                der_signature = signature

            # Verify the signature
            public_key.verify(der_signature, data, ec.ECDSA(hashes.SHA256()))

            return True

        except InvalidSignature:
            logger.error("WebAuthn EC signature verification failed: invalid signature")
            raise ValueError("Signature verification failed")
        except Exception as e:
            logger.error(f"WebAuthn EC signature verification error: {e}")
            raise ValueError(f"Signature verification failed: {e}")

    def _verify_webauthn_signature(
        self,
        public_key_cose: bytes,
        authenticator_data: bytes,
        client_data_hash: bytes,
        signature: bytes,
    ) -> bool:
        """
        Verify a WebAuthn authentication signature.

        The signature is computed over: authenticator_data || SHA256(client_data_json)

        Args:
            public_key_cose: The stored public key in COSE format
            authenticator_data: Raw authenticator data bytes
            client_data_hash: SHA256 hash of client data JSON
            signature: The signature bytes

        Returns:
            True if signature is valid

        Raises:
            ValueError: If verification fails
        """
        # The signed data is authenticator_data || client_data_hash
        signed_data = authenticator_data + client_data_hash

        # Parse COSE key to determine algorithm
        try:
            cose_key = self._parse_cose_key(public_key_cose)
        except ValueError as e:
            logger.error(f"Failed to parse COSE key: {e}")
            raise ValueError("Invalid public key format")

        # Verify the parsed key is a dict (COSE keys are CBOR maps)
        if not isinstance(cose_key, dict):
            logger.error(
                f"COSE key parsing returned unexpected type: {type(cose_key).__name__}. "
                "The stored public key may not be in COSE format. "
                "Re-register the passkey to fix this issue."
            )
            raise ValueError("Invalid public key format: expected COSE key map")

        kty = cose_key.get(1)  # Key type
        alg = cose_key.get(3)  # Algorithm

        if kty == COSE_KTY_EC2 and alg == COSE_ALG_ES256:
            return self._verify_signature_ec(public_key_cose, signature, signed_data, alg)
        else:
            # For other algorithms, we'd need additional implementations
            # Currently only ES256 is supported
            raise ValueError(f"Unsupported key type/algorithm: kty={kty}, alg={alg}")

    # ==================
    # Registration Flow
    # ==================

    def create_registration_options(
        self,
        user_verification: str = "preferred",
        authenticator_attachment: str = None,
        require_resident_key: bool = True,
    ) -> Tuple[Dict[str, Any], str]:
        """
        Create registration options for passkey enrollment.

        Args:
            user_verification: 'required', 'preferred', or 'discouraged'
            authenticator_attachment: 'platform', 'cross-platform', or None (any)
            require_resident_key: Whether to require a discoverable credential

        Returns:
            Tuple of (registration_options, challenge)
        """
        if not self.user:
            raise ValueError("User is required for registration")
        if user_verification not in {"required", "preferred", "discouraged"}:
            raise ValueError("Invalid user verification policy")

        # Create challenge
        challenge_record = WebAuthnChallenge.create_challenge(
            user=self.user,
            challenge_type="registration",
            ttl_seconds=self.CHALLENGE_TTL,
        )
        challenge_record.user_verification = user_verification
        challenge_record.save(update_fields=["user_verification"])

        # Get existing credentials to exclude
        existing_credentials = UserPasskey.objects.filter(
            user=self.user,
            is_active=True,
        ).values_list("credential_id", flat=True)

        exclude_credentials = [
            {
                "id": cred_id,
                "type": "public-key",
            }
            for cred_id in existing_credentials
        ]

        # Build options
        options = {
            "challenge": challenge_record.challenge,
            "rp": {
                "name": self.rp_name,
                "id": self.rp_id,
            },
            "user": {
                "id": self._encode_user_id(self.user),
                "name": self.user.email,
                "displayName": self._get_user_display_name(),
            },
            "pubKeyCredParams": [
                {"type": "public-key", "alg": -7},  # ES256
            ],
            "timeout": self.CHALLENGE_TTL * 1000,  # milliseconds
            "attestation": "none",  # We don't need attestation for most use cases
            "authenticatorSelection": {
                "userVerification": user_verification,
                "residentKey": "required" if require_resident_key else "preferred",
                "requireResidentKey": require_resident_key,
            },
            "excludeCredentials": exclude_credentials,
        }

        if authenticator_attachment:
            options["authenticatorSelection"]["authenticatorAttachment"] = authenticator_attachment

        return options, challenge_record.challenge

    @transaction.atomic
    def verify_registration(
        self,
        challenge: str,
        credential_id: str,
        attestation_object: str,
        client_data_json: str,
        name: str = "My Passkey",
        transports: List[str] = None,
        ip_address: str = None,
        public_key: str = None,
    ) -> UserPasskey:
        """
        Verify a registration response and create the passkey.

        Args:
            challenge: The original challenge
            credential_id: Base64url-encoded credential ID
            public_key: Ignored legacy client field; keys are extracted from authenticator data
            attestation_object: Base64url-encoded attestation object
            client_data_json: Base64url-encoded client data JSON
            name: User-provided name for the passkey
            transports: List of transports supported by the authenticator
            ip_address: Request IP for audit

        Returns:
            Created UserPasskey instance

        Raises:
            ValueError: If verification fails
        """
        if not self.user:
            raise ValueError("User is required for registration")

        # Find and validate challenge
        challenge_record = (
            WebAuthnChallenge.objects.select_for_update()
            .filter(
                user=self.user,
                challenge=challenge,
                challenge_type="registration",
            )
            .first()
        )

        if not challenge_record:
            raise ValueError("Challenge not found")

        if not challenge_record.is_valid:
            raise ValueError("Challenge expired or already used")

        # Browser getPublicKey() returns SPKI, not COSE. Never trust that separate field.
        # The verifier checks challenge, origin, RP hash, flags, credential ID and algorithm,
        # and extracts the actual COSE credential key from the attestation object's authData.
        try:
            client_data = json.loads(base64url_to_bytes(client_data_json))
            if client_data.get("crossOrigin", False) is not False:
                raise ValueError("Cross-origin registration is not supported")
            verification = verify_registration_response(
                credential={
                    "id": credential_id,
                    "rawId": credential_id,
                    "type": "public-key",
                    "response": {
                        "attestationObject": attestation_object,
                        "clientDataJSON": client_data_json,
                    },
                },
                expected_challenge=base64url_to_bytes(challenge_record.challenge),
                expected_rp_id=self.rp_id,
                expected_origin=self._get_allowed_origins(),
                require_user_presence=True,
                require_user_verification=challenge_record.user_verification == "required",
                supported_pub_key_algs=[COSEAlgorithmIdentifier.ECDSA_SHA_256],
            )
            if verification.credential_id != base64url_to_bytes(credential_id):
                raise ValueError("Credential ID mismatch")
            cose_key = self._parse_cose_key(verification.credential_public_key)
            if cose_key.get(1) != COSE_KTY_EC2 or cose_key.get(-1) != 1:
                raise ValueError("Unsupported credential curve")
            ec.EllipticCurvePublicNumbers(
                int.from_bytes(cose_key[-2], "big"), int.from_bytes(cose_key[-3], "big"), ec.SECP256R1()
            ).public_key()
        except Exception as e:
            raise ValueError("Passkey registration verification failed") from e

        # Create passkey
        try:
            with transaction.atomic():
                passkey = UserPasskey.objects.create(
                    user=self.user,
                    credential_id=bytes_to_base64url(verification.credential_id),
                    name=name,
                    public_key=bytes_to_base64url(verification.credential_public_key),
                    sign_count=verification.sign_count,
                    aaguid=verification.aaguid,
                    transports=transports or [],
                    authenticator_type="platform" if "internal" in (transports or []) else "cross-platform",
                    registered_from_ip=ip_address,
                )
        except IntegrityError as e:
            raise ValueError("Passkey is already registered") from e

        challenge_record.mark_used()

        # Log event
        SSOAuditLog.log_event(
            event_type=SSOAuditEventType.PASSKEY_REGISTERED,
            user=self.user,
            description=f'Passkey "{name}" registered',
            ip_address=ip_address,
            metadata={"passkey_id": str(passkey.pk)},
        )

        return passkey

    # ==================
    # Authentication Flow
    # ==================

    @transaction.atomic
    def create_authentication_options(
        self,
        user_verification: str = "required",
        browser_binding: str = "",
    ) -> Tuple[Dict[str, Any], str]:
        """
        Create authentication options for passkey login.

        Args:
            user_verification: Legacy client preference; passwordless login always requires verification

        Returns:
            Tuple of (authentication_options, challenge)
        """
        # Passwordless login policy belongs to the server, not the client.
        user_verification = "required"
        # Create challenge
        challenge_record = WebAuthnChallenge.create_challenge(
            user=self.user,  # May be None for discoverable credentials
            challenge_type="authentication",
            ttl_seconds=self.CHALLENGE_TTL,
        )
        challenge_record.user_verification = user_verification
        challenge_record.browser_binding = browser_binding
        challenge_record.save(update_fields=["user_verification", "browser_binding"])

        options = {
            "challenge": challenge_record.challenge,
            "timeout": self.CHALLENGE_TTL * 1000,
            "rpId": self.rp_id,
            "userVerification": user_verification,
        }

        # If user is known, provide allowed credentials
        if self.user:
            credentials = UserPasskey.objects.filter(
                user=self.user,
                is_active=True,
            ).values("credential_id", "transports")

            options["allowCredentials"] = [
                {
                    "id": cred["credential_id"],
                    "type": "public-key",
                    "transports": cred["transports"] or [],
                }
                for cred in credentials
            ]

        return options, challenge_record.challenge

    def verify_authentication(
        self,
        challenge: str,
        credential_id: str,
        authenticator_data: str,
        client_data_json: str,
        signature: str,
        user_handle: str = None,
        ip_address: str = None,
        challenge_type: str = "authentication",
        browser_binding: str = None,
    ) -> Tuple[User, UserPasskey]:
        """
        Verify an authentication response with full cryptographic validation.

        Security validations performed:
        1. Challenge validation (replay protection)
        2. Origin verification
        3. Cryptographic signature verification using stored public key
        4. Sign count verification (cloned authenticator detection)

        Args:
            challenge: The original challenge
            credential_id: Base64url-encoded credential ID
            authenticator_data: Base64url-encoded authenticator data
            client_data_json: Base64url-encoded client data JSON
            signature: Base64url-encoded signature
            user_handle: Base64url-encoded user handle (for discoverable credentials)
            ip_address: Request IP for audit

        Returns:
            Tuple of (user, passkey)

        Raises:
            ValueError: If verification fails
        """
        # Commit deliberate rejection effects (audit/deactivation) before raising.
        # Unexpected failures still roll back challenge consumption and counter writes.
        error = None
        with transaction.atomic():
            try:
                result = self._verify_authentication_locked(
                    challenge,
                    credential_id,
                    authenticator_data,
                    client_data_json,
                    signature,
                    user_handle,
                    ip_address,
                    challenge_type,
                    browser_binding,
                )
            except ValueError as exc:
                owner = self.user
                if owner is None and isinstance(credential_id, str) and len(credential_id) <= 2048:
                    credential = UserPasskey.objects.select_related('user').filter(credential_id=credential_id).first()
                    owner = credential.user if credential else None
                SSOAuditLog.log_event(
                    event_type=SSOAuditEventType.PASSKEY_AUTH_FAILED,
                    user=owner,
                    description="Passkey assertion rejected",
                    ip_address=ip_address,
                    success=False,
                    metadata={"operation": "authentication", "reason": "assertion_rejected"},
                )
                error = exc
            else:
                user, passkey, challenge_record, new_sign_count = result
                challenge_record.mark_used()
                passkey.record_use(new_sign_count)
                SSOAuditLog.log_event(
                    event_type=SSOAuditEventType.PASSKEY_AUTH_SUCCESS,
                    user=user,
                    description=f'Authenticated with passkey "{passkey.name}"',
                    ip_address=ip_address,
                )
        if error is not None:
            raise error
        return user, passkey

    def _verify_authentication_locked(
        self,
        challenge,
        credential_id,
        authenticator_data,
        client_data_json,
        signature,
        user_handle,
        ip_address,
        challenge_type,
        browser_binding,
    ):
        # Match the management flow's lock order: challenge, then credential.
        challenge_record = (
            WebAuthnChallenge.objects.select_for_update()
            .filter(
                challenge=challenge,
                challenge_type=challenge_type,
            )
            .first()
        )
        if not challenge_record:
            raise ValueError("Challenge not found")

        passkey = (
            UserPasskey.objects.select_for_update(of=("self",))
            .filter(
                credential_id=credential_id,
                is_active=True,
            )
            .select_related("user")
            .first()
        )
        if not passkey:
            raise ValueError("Passkey not found")
        user = passkey.user
        # An active credential must never authenticate a disabled account.
        # Read the owner from the database rather than trusting self.user.
        if not user.is_active:
            raise ValueError("Authentication failed")

        if not challenge_record.is_valid:
            raise ValueError("Challenge expired or already used")

        if challenge_record.user_id is not None and challenge_record.user_id != user.pk:
            raise ValueError("Credential owner does not match challenge")
        if self.user is not None and self.user.pk != user.pk:
            raise ValueError("Credential owner does not match user")

        # HTTP login requires a binding, including for challenges issued before
        # this protection existed. Bound challenges cannot be used by direct callers.
        if (browser_binding is not None or challenge_record.browser_binding) and (
            not browser_binding
            or not challenge_record.browser_binding
            or not secrets.compare_digest(browser_binding, challenge_record.browser_binding)
        ):
            raise ValueError("Authentication failed")

        # Discoverable credentials must identify their owner; identified-user flows
        # may omit the handle, but any supplied handle must still match the owner.
        if challenge_record.user_id is None and self.user is None and user_handle is None:
            raise ValueError("User handle is required")
        if user_handle is not None:
            try:
                handle_bytes = base64.b64decode(
                    user_handle + "=" * (-len(user_handle) % 4), altchars=b"-_", validate=True
                )
            except (ValueError, TypeError) as e:
                raise ValueError("Invalid user handle") from e
            if handle_bytes != str(user.pk).encode("utf-8"):
                raise ValueError("User handle does not match credential owner")

        # Decode client data
        try:
            client_data_bytes = base64.urlsafe_b64decode(client_data_json + "=" * (-len(client_data_json) % 4))
            client_data = json.loads(client_data_bytes)
            if not isinstance(client_data, dict):
                raise ValueError("Client data must be an object")
        except Exception as e:
            raise ValueError(f"Invalid client data: {e}")

        # Verify challenge
        if client_data.get("challenge") != challenge:
            raise ValueError("Challenge mismatch")

        # SECURITY: Verify origin (always enforced)
        actual_origin = client_data.get("origin", "")
        self._verify_origin(actual_origin)

        # Verify type
        if client_data.get("type") != "webauthn.get":
            raise ValueError("Invalid client data type")
        if client_data.get("crossOrigin", False) is not False:
            raise ValueError("Cross-origin authentication is not supported")

        # Decode authenticator data and signature
        try:
            auth_data_bytes = base64.urlsafe_b64decode(authenticator_data + "=" * (-len(authenticator_data) % 4))
            signature_bytes = base64.urlsafe_b64decode(signature + "=" * (-len(signature) % 4))
            parsed_auth_data = parse_authenticator_data(auth_data_bytes)
            parse_backup_flags(parsed_auth_data.flags)
        except Exception as e:
            raise ValueError("Invalid authenticator data or signature") from e

        if parsed_auth_data.rp_id_hash != hashlib.sha256(self.rp_id.encode("utf-8")).digest():
            raise ValueError("RP ID hash mismatch")
        if not parsed_auth_data.flags.up:
            raise ValueError("User presence is required")
        # Enforce the server policy even for challenges issued before this change.
        if not parsed_auth_data.flags.uv:
            raise ValueError("User verification is required")

        # SECURITY: Verify the cryptographic signature
        # Signature is over: authenticator_data || SHA256(client_data_json)
        client_data_hash = hashlib.sha256(client_data_bytes).digest()

        try:
            # Decode the stored public key
            public_key_bytes = base64.urlsafe_b64decode(passkey.public_key + "=" * (-len(passkey.public_key) % 4))

            # Verify the signature
            self._verify_webauthn_signature(
                public_key_cose=public_key_bytes,
                authenticator_data=auth_data_bytes,
                client_data_hash=client_data_hash,
                signature=signature_bytes,
            )
            logger.debug(f"WebAuthn signature verification successful for user {user.email}")
        except ValueError:
            # Log the authentication failure
            raise ValueError("Authentication failed: signature verification failed")

        new_sign_count = parsed_auth_data.sign_count

        # SECURITY: Verify sign count (protection against cloned authenticators)
        strict_sign_count = getattr(settings, "WEBAUTHN_STRICT_SIGN_COUNT", True)

        if new_sign_count <= passkey.sign_count and passkey.sign_count > 0:
            logger.error(
                f"SECURITY ALERT: Passkey sign count anomaly detected for user {user.email}. "
                f"Expected > {passkey.sign_count}, got {new_sign_count}. "
                f"This may indicate a cloned authenticator!"
            )

            # Log security event
            SSOAuditLog.log_event(
                event_type=SSOAuditEventType.PASSKEY_CLONE_DETECTED,
                user=user,
                description="Sign count anomaly detected - possible cloned authenticator",
                ip_address=ip_address,
                success=False,
                metadata={
                    "expected_sign_count": passkey.sign_count,
                    "received_sign_count": new_sign_count,
                    "passkey_name": passkey.name,
                    "credential_id_prefix": credential_id[:8] if credential_id else "unknown",
                },
            )

            if strict_sign_count:
                # Deactivate the potentially compromised passkey
                passkey.deactivate()
                raise ValueError(
                    "Authentication rejected: security anomaly detected. "
                    "Please re-register your passkey or contact support."
                )
            else:
                logger.warning(
                    "Sign count anomaly allowed (WEBAUTHN_STRICT_SIGN_COUNT=False). "
                    "This is not recommended for production use."
                )

        return user, passkey, challenge_record, new_sign_count

    # ==================
    # Management
    # ==================

    def list_passkeys(self) -> List[UserPasskey]:
        """List all passkeys for the current user."""
        if not self.user:
            raise ValueError("User is required")

        return list(
            UserPasskey.objects.filter(
                user=self.user,
                is_active=True,
            ).order_by("-created_at")
        )

    def delete_passkey(self, passkey_id: str, ip_address: str = None) -> bool:
        """
        Delete a passkey.

        Args:
            passkey_id: The passkey ID to delete
            ip_address: Request IP for audit

        Returns:
            True if deleted
        """
        if not self.user:
            raise ValueError("User is required")

        passkey = UserPasskey.objects.filter(
            id=passkey_id,
            user=self.user,
        ).first()

        if not passkey:
            raise ValueError("Passkey not found")

        name = passkey.name
        passkey.deactivate()

        SSOAuditLog.log_event(
            event_type=SSOAuditEventType.PASSKEY_REMOVED,
            user=self.user,
            description=f'Passkey "{name}" removed',
            ip_address=ip_address,
        )

        return True

    def rename_passkey(self, passkey_id: str, new_name: str) -> UserPasskey:
        """
        Rename a passkey.

        Args:
            passkey_id: The passkey ID
            new_name: New name for the passkey

        Returns:
            Updated passkey
        """
        if not self.user:
            raise ValueError("User is required")

        passkey = UserPasskey.objects.filter(
            id=passkey_id,
            user=self.user,
            is_active=True,
        ).first()

        if not passkey:
            raise ValueError("Passkey not found")

        passkey.name = new_name
        passkey.save(update_fields=["name", "updated_at"])

        return passkey

    # ==================
    # Helpers
    # ==================

    def _encode_user_id(self, user: User) -> str:
        """Encode user ID for WebAuthn."""
        return base64.urlsafe_b64encode(str(user.id).encode("utf-8")).rstrip(b"=").decode("utf-8")

    def _get_user_display_name(self) -> str:
        """Get user display name for WebAuthn."""
        if hasattr(self.user, "profile") and self.user.profile:
            name = f"{self.user.profile.first_name} {self.user.profile.last_name}".strip()
            if name:
                return name
        return self.user.email
