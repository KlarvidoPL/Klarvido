"""Sanitize AWS X-Ray entities at the final export boundary."""
import json
import logging

from aws_xray_sdk.core.emitters.udp_emitter import UDPEmitter, PROTOCOL_HEADER, PROTOCOL_DELIMITER
from .redaction import _redact

logger = logging.getLogger(__name__)


class CredentialSafeEmitter(UDPEmitter):
    def send_entity(self, entity):
        try:
            document = _redact(json.loads(entity.serialize()))
            self._send_data(PROTOCOL_HEADER + PROTOCOL_DELIMITER + json.dumps(document))
        except Exception:
            # Dropping telemetry is safer than exporting an unredacted fallback.
            logger.error('Unable to export sanitized tracing entity')
