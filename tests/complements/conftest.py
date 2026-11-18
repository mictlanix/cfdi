"""The shared check every document-type and complement test makes."""

import base64
from collections.abc import Callable
from typing import Any

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from lxml import etree

from mictlanix.cfdi import CSD, Comprobante, RawXml, _sat, original_string, seal, validate

BuildsValidatesSeals = Callable[[Comprobante], str]


def _schema_urls(comprobante: Comprobante) -> tuple[str, ...]:
    models: list[Any] = [comprobante, *comprobante.Complemento]
    for concepto in comprobante.Conceptos:
        models.extend(concepto.ComplementoConcepto)
    return tuple(
        sorted(
            {
                m.__xml__.schema_location
                for m in models
                if not isinstance(m, RawXml) and m.__xml__.schema_location
            }
        )
    )


def assert_builds_validates_seals(comprobante: Comprobante, csd: CSD) -> str:
    """Validate, seal, check the sealed XML against the SAT's XSDs and verify the seal.

    Returns the sealed document's original string, for the caller's own checks.
    """
    assert validate(comprobante) == []
    sealed = seal(comprobante, csd)
    root = etree.fromstring(sealed)
    schema = _sat.schema(_schema_urls(comprobante))
    assert schema.validate(root), schema.error_log
    certificate = x509.load_der_x509_certificate(base64.b64decode(root.get('Certificado', '')))
    public = certificate.public_key()
    assert isinstance(public, rsa.RSAPublicKey)
    cadena = original_string(sealed)
    public.verify(
        base64.b64decode(root.get('Sello', '')),
        cadena.encode('utf-8'),
        padding.PKCS1v15(),
        hashes.SHA256(),
    )
    return cadena


@pytest.fixture
def builds_validates_seals(csd: CSD) -> BuildsValidatesSeals:
    """``assert_builds_validates_seals`` with the SAT's public test CSD."""
    return lambda comprobante: assert_builds_validates_seals(comprobante, csd)
