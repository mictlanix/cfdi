"""The issuer's Certificado de Sello Digital (CSD)."""

from __future__ import annotations

from datetime import datetime

from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.hazmat.primitives.serialization import Encoding, load_der_private_key

from mictlanix.cfdi._errors import CsdError
from mictlanix.cfdi._mexico import MEXICO_CITY

_Reason = CsdError.Reason


class CSD:
    """A certificate and its private key, loaded from the caller's ``.cer`` and ``.key`` bytes.

    Only the certificate number and validity period are public. The key stays private, the
    password is not stored, and ``repr`` never shows key material.
    """

    __slots__ = ('NoCertificado', '_certificate', '_key', 'valid_from', 'valid_to')

    NoCertificado: str
    valid_from: datetime
    valid_to: datetime

    def __init__(self, certificate: x509.Certificate, key: rsa.RSAPrivateKey) -> None:
        self._certificate = certificate
        self._key = key
        self.NoCertificado = _certificate_number(certificate)
        self.valid_from = _local(certificate.not_valid_before_utc)
        self.valid_to = _local(certificate.not_valid_after_utc)

    @classmethod
    def load(cls, certificate: bytes, private_key: bytes, password: str) -> CSD:
        """Load a CSD. ``certificate`` is the ``.cer`` (DER); ``private_key`` the ``.key``.

        The key must be encrypted PKCS#8 (DER), as the SAT issues it. Raises ``CsdError``.
        """
        try:
            parsed = x509.load_der_x509_certificate(certificate)
        except ValueError:
            raise CsdError(_Reason.INVALID_CERTIFICATE) from None
        key = _load_key(private_key, password.encode('utf-8'))
        if not isinstance(key, rsa.RSAPrivateKey):
            raise CsdError(_Reason.INVALID_KEY)
        public = parsed.public_key()
        if not isinstance(public, rsa.RSAPublicKey) or (
            public.public_numbers() != key.public_key().public_numbers()
        ):
            raise CsdError(_Reason.KEY_MISMATCH)
        return cls(parsed, key)

    def __repr__(self) -> str:
        return (
            f'CSD(NoCertificado={self.NoCertificado!r}, '
            f'valid_from={self.valid_from.isoformat()}, valid_to={self.valid_to.isoformat()})'
        )

    def certificate_der(self) -> bytes:
        return self._certificate.public_bytes(Encoding.DER)

    def sign(self, data: bytes) -> bytes:
        """RSA PKCS#1 v1.5 signature of ``data`` with SHA-256."""
        return self._key.sign(data, padding.PKCS1v15(), hashes.SHA256())


def _local(moment: datetime) -> datetime:
    """The certificate's UTC time as naive Mexico City time."""
    return moment.astimezone(MEXICO_CITY).replace(tzinfo=None)


def _certificate_number(certificate: x509.Certificate) -> str:
    """The SAT certificate number: the serial's bytes read as 20 ASCII digits."""
    serial = certificate.serial_number
    raw = serial.to_bytes((serial.bit_length() + 7) // 8, 'big')
    try:
        number = raw.decode('ascii')
    except UnicodeDecodeError:
        raise CsdError(_Reason.INVALID_CERTIFICATE) from None
    if len(number) != 20 or not number.isdigit():
        raise CsdError(_Reason.INVALID_CERTIFICATE)
    return number


def _load_key(private_key: bytes, password: bytes) -> object:
    try:
        return load_der_private_key(private_key, password)
    except TypeError:
        # The key is not encrypted; the SAT always issues encrypted keys.
        raise CsdError(_Reason.INVALID_KEY) from None
    except ValueError:
        pass
    try:
        load_der_private_key(private_key, None)
    except TypeError:
        # Well-formed and encrypted, so the password is what failed.
        raise CsdError(_Reason.WRONG_PASSWORD) from None
    except ValueError:
        raise CsdError(_Reason.INVALID_KEY) from None
    raise CsdError(_Reason.INVALID_KEY)
