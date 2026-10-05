"""KSeF sessions and encrypted invoice exports. Credentials never leave the worker."""
import base64
import hashlib
import io
import json
import os
import zipfile
from urllib.parse import urlparse
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime

import httpx
from cryptography import x509
from cryptography.hazmat.primitives import hashes, padding as symmetric_padding
from cryptography.hazmat.primitives.asymmetric import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from apps.ksef import client, crypto

MAX_PACKAGE_BYTES = 256 * 1024 * 1024


def retry_after(response):
    value = response.headers.get('Retry-After', '60')
    try:
        return max(1, int(value))
    except ValueError:
        try:
            return max(1, int((parsedate_to_datetime(value) - datetime.now(timezone.utc)).total_seconds()))
        except (ValueError, TypeError):
            return 60


class KsefSyncError(Exception):
    def __init__(self, code, retry_after=0):
        self.code = code
        self.retry_after = retry_after
        super().__init__(code)


class KsefSession:
    def __init__(self, nip, token, http=None):
        self.nip, self.token = nip, token
        self.http = http or httpx.Client(base_url=client._base_url(), timeout=30)
        self.owns_http = http is None
        self.access = self.refresh = ''

    def request(self, method, path, **kwargs):
        response = self.http.request(method, path, headers=client._bearer(self.access) if self.access else {}, **kwargs)
        if response.status_code == 401 and self.refresh:
            refreshed = self.http.post('/auth/token/refresh', headers=client._bearer(self.refresh))
            if refreshed.status_code != 200:
                raise KsefSyncError('INVALID_TOKEN')
            self.access = refreshed.json()['accessToken']['token']
            response = self.http.request(method, path, headers=client._bearer(self.access), **kwargs)
        if response.status_code == 429:
            raise KsefSyncError('RATE_LIMITED', retry_after(response))
        if response.status_code >= 500:
            raise KsefSyncError('SERVICE_UNAVAILABLE', 60)
        if response.status_code == 403:
            raise KsefSyncError('NO_PERMISSIONS')
        if response.status_code == 401:
            raise KsefSyncError('INVALID_TOKEN')
        if response.status_code >= 400:
            raise KsefSyncError('KSEF_REQUEST_REJECTED')
        return response

    def __enter__(self):
        try:
            certificates = self.request('GET', '/security/public-key-certificates').json()
            self.certificates = certificates
            key_id, key = client._encryption_certificate_key(self.http)
            challenge = self.request('POST', '/auth/challenge').json()
            auth = self.request(
                'POST',
                '/auth/ksef-token',
                json={
                    'challenge': challenge['challenge'],
                    'contextIdentifier': {'type': 'Nip', 'value': self.nip},
                    'encryptedToken': client._encrypt_token(key, self.token, challenge['timestampMs']),
                    'publicKeyId': key_id,
                },
            ).json()
            client._wait_for_authentication(self.http, auth['referenceNumber'], auth['authenticationToken']['token'])
            tokens = self.http.post('/auth/token/redeem', headers=client._bearer(auth['authenticationToken']['token']))
            if tokens.status_code != 200:
                raise KsefSyncError('SERVICE_UNAVAILABLE', 60)
            self.access = tokens.json()['accessToken']['token']
            self.refresh = tokens.json().get('refreshToken', {}).get('token', '')
            return self
        except client._Rejected as exc:
            self.close()
            raise KsefSyncError(str(exc.error_code)) from exc
        except client._Unavailable as exc:
            self.close()
            raise KsefSyncError('SERVICE_UNAVAILABLE', 60) from exc
        except Exception:
            self.close()
            raise
        finally:
            self.token = ''

    def close(self):
        if self.access:
            client._close_session(self.http, self.access)
        if self.owns_http:
            self.http.close()

    def __exit__(self, *_):
        self.close()

    def start_export(self, subject, start, tenant_id, end=None):
        now = datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')
        candidates = [
            c
            for c in self.certificates
            if client._has_usage(c, 'SymmetricKeyEncryption')
            and c.get('validFrom', '')[:19] <= now < c.get('validTo', '')[:19]
        ]
        if not candidates:
            raise KsefSyncError('SERVICE_UNAVAILABLE', 60)
        certificate = max(candidates, key=lambda c: c.get('validFrom', ''))
        key = x509.load_der_x509_certificate(base64.b64decode(certificate['certificate'])).public_key()
        aes_key, iv = os.urandom(32), os.urandom(16)
        encrypted = key.encrypt(
            aes_key, padding.OAEP(mgf=padding.MGF1(hashes.SHA256()), algorithm=hashes.SHA256(), label=None)
        )
        body = self.request(
            'POST',
            '/invoices/exports',
            json={
                'encryption': {
                    'encryptedSymmetricKey': base64.b64encode(encrypted).decode(),
                    'initializationVector': base64.b64encode(iv).decode(),
                    'publicKeyId': certificate['publicKeyId'],
                },
                'filters': {
                    'subjectType': subject,
                    'dateRange': {
                        'dateType': 'PermanentStorage',
                        'from': start,
                        'to': end,
                        'restrictToPermanentStorageHwmDate': True,
                    },
                },
            },
        ).json()
        secret = crypto.encrypt_token(tenant_id, json.dumps({'key': aes_key.hex(), 'iv': iv.hex()})).hex()
        return {'reference': body['referenceNumber'], 'secret': secret, 'subject': subject}

    def export_status(self, pending):
        result = self.request('GET', '/invoices/exports/' + pending['reference']).json()
        code = result['status']['code']
        if code == 100:
            return None
        if code == 210:
            raise KsefSyncError('EXPORT_EXPIRED', 60)
        if code == 420:
            raise KsefSyncError('HWM_NOT_READY', 120)
        if code != 200:
            raise KsefSyncError('EXPORT_FAILED', 60 if code >= 500 else 0)
        return result['package']

    def read_package(self, package, pending, tenant_id):
        if package.get('invoiceCount') == 0 and not package.get('parts'):
            return []
        secret = json.loads(crypto.decrypt_token(tenant_id, bytes.fromhex(pending['secret'])))
        archive = io.BytesIO()
        # Do not send KSeF Authorization to package storage URLs.
        with httpx.Client(timeout=60, follow_redirects=False) as download:
            for part in sorted(package['parts'], key=lambda p: p['ordinalNumber']):
                url = urlparse(part['url'])
                host = url.hostname or ''
                if url.scheme != 'https' or not (host.endswith(('.blob.core.windows.net', '.mf.gov.pl'))):
                    raise KsefSyncError('INVALID_PACKAGE_URL')
                if part['method'] != 'GET' or part['encryptedPartSize'] > MAX_PACKAGE_BYTES:
                    raise KsefSyncError('INVALID_PACKAGE')
                encrypted = bytearray()
                with download.stream('GET', part['url']) as response:
                    if response.status_code == 429:
                        raise KsefSyncError('RATE_LIMITED', retry_after(response))
                    if response.status_code != 200:
                        raise KsefSyncError('PACKAGE_DOWNLOAD_FAILED', 60)
                    for chunk in response.iter_bytes():
                        encrypted.extend(chunk)
                        if len(encrypted) > MAX_PACKAGE_BYTES:
                            raise KsefSyncError('PACKAGE_TOO_LARGE')
                if base64.b64encode(hashlib.sha256(encrypted).digest()).decode() != part['encryptedPartHash']:
                    raise KsefSyncError('PACKAGE_HASH_MISMATCH')
                decryptor = Cipher(
                    algorithms.AES(bytes.fromhex(secret['key'])), modes.CBC(bytes.fromhex(secret['iv']))
                ).decryptor()
                plain = decryptor.update(bytes(encrypted)) + decryptor.finalize()
                unpadder = symmetric_padding.PKCS7(128).unpadder()
                plain = unpadder.update(plain) + unpadder.finalize()
                if base64.b64encode(hashlib.sha256(plain).digest()).decode() != part['partHash']:
                    raise KsefSyncError('PACKAGE_HASH_MISMATCH')
                archive.write(plain)
                if archive.tell() > MAX_PACKAGE_BYTES:
                    raise KsefSyncError('PACKAGE_TOO_LARGE')
        archive.seek(0)
        with zipfile.ZipFile(archive) as zipped:
            if sum(i.file_size for i in zipped.infolist()) > MAX_PACKAGE_BYTES:
                raise KsefSyncError('PACKAGE_TOO_LARGE')
            metadata = json.loads(zipped.read('_metadata.json'))['invoices']
            return [(meta, zipped.read(meta['ksefNumber'] + '.xml').decode('utf-8-sig')) for meta in metadata]
