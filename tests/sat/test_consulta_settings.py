"""The SAT status settings: immutable, HTTPS only, positive timeouts."""

from dataclasses import FrozenInstanceError

import pytest

from mictlanix.cfdi.sat import SatConsultaSettings


def test_defaults() -> None:
    settings = SatConsultaSettings()
    assert settings.url == (
        'https://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'
    )
    assert settings.connect_timeout == 10.0
    assert settings.read_timeout == 60.0


def test_frozen_and_keyword_only() -> None:
    settings = SatConsultaSettings()
    with pytest.raises(FrozenInstanceError):
        settings.url = 'https://x.test'  # type: ignore[misc]
    with pytest.raises(TypeError):
        SatConsultaSettings('https://x.test')  # type: ignore[misc]


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('url', 'http://consultaqr.facturaelectronica.sat.gob.mx/ConsultaCFDIService.svc'),
        ('url', 'consultaqr.facturaelectronica.sat.gob.mx'),
        ('connect_timeout', 0.0),
        ('read_timeout', -1.0),
    ],
)
def test_invalid_values_are_refused_naming_the_field(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        SatConsultaSettings(**{field: value})  # type: ignore[arg-type]
