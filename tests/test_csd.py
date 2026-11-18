import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID

from mictlanix.cfdi import CSD, CsdError
from tests.conftest import CsdFiles


def _key(password: bytes | None) -> tuple[rsa.RSAPrivateKey, bytes]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    encryption = (
        serialization.BestAvailableEncryption(password)
        if password
        else serialization.NoEncryption()
    )
    der = key.private_bytes(
        serialization.Encoding.DER, serialization.PrivateFormat.PKCS8, encryption
    )
    return key, der


def _certificate(key: rsa.RSAPrivateKey, serial: int) -> bytes:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, 'PRUEBA')])
    now = datetime.now(UTC)
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(serial)
        .not_valid_before(now - timedelta(days=1))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    return certificate.public_bytes(serialization.Encoding.DER)


def test_load_gives_the_certificate_number_and_validity(csd: CSD) -> None:
    assert csd.NoCertificado == '30001000000500003416'
    # The certificate says 11:43:51Z; Mexico City local time is a fixed UTC-6.
    assert csd.valid_from == datetime(2023, 5, 18, 5, 43, 51)
    assert csd.valid_to == datetime(2027, 5, 18, 5, 43, 51)
    assert csd.valid_from.tzinfo is None and csd.valid_to.tzinfo is None


def test_repr_shows_only_the_public_fields(csd: CSD) -> None:
    assert repr(csd) == (
        "CSD(NoCertificado='30001000000500003416', "
        'valid_from=2023-05-18T05:43:51, valid_to=2027-05-18T05:43:51)'
    )


def _assert_reason(
    caught: pytest.ExceptionInfo[CsdError], reason: str, *secrets: bytes | str
) -> None:
    error = caught.value
    assert error.reason == reason
    for secret in secrets:
        text = secret if isinstance(secret, str) else base64.b64encode(secret).decode()
        assert text not in str(error) and text not in repr(error)
        if isinstance(secret, bytes):
            assert secret.hex() not in str(error) and secret.hex() not in repr(error)
    assert error.__cause__ is None


def test_a_wrong_password(csd_files: CsdFiles) -> None:
    with pytest.raises(CsdError) as caught:
        CSD.load(csd_files.certificate, csd_files.private_key, 'not-the-password')
    _assert_reason(caught, 'wrong_password', 'not-the-password', csd_files.private_key)


def test_a_key_that_belongs_to_another_certificate(csd_files: CsdFiles) -> None:
    _, other = _key(csd_files.password.encode())
    with pytest.raises(CsdError) as caught:
        CSD.load(csd_files.certificate, other, csd_files.password)
    _assert_reason(caught, 'key_mismatch', csd_files.password, other)


def test_bytes_that_are_not_a_certificate(csd_files: CsdFiles) -> None:
    with pytest.raises(CsdError) as caught:
        CSD.load(b'not a certificate', csd_files.private_key, csd_files.password)
    _assert_reason(caught, 'invalid_certificate', csd_files.password, csd_files.private_key)


def test_bytes_that_are_not_a_key(csd_files: CsdFiles) -> None:
    with pytest.raises(CsdError) as caught:
        CSD.load(csd_files.certificate, b'not a key', csd_files.password)
    _assert_reason(caught, 'invalid_key', csd_files.password)


def test_a_key_that_is_not_encrypted(csd_files: CsdFiles) -> None:
    _, plain = _key(None)
    with pytest.raises(CsdError) as caught:
        CSD.load(csd_files.certificate, plain, csd_files.password)
    _assert_reason(caught, 'invalid_key', csd_files.password, plain)


def test_a_certificate_that_is_not_a_sat_csd(csd_files: CsdFiles) -> None:
    key, der = _key(b'secreto')
    with pytest.raises(CsdError) as caught:
        CSD.load(_certificate(key, 12345), der, 'secreto')
    _assert_reason(caught, 'invalid_certificate', 'secreto', der)
