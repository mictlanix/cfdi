"""The Multifacturas settings: immutable, HTTPS only, the password never printed."""

from dataclasses import FrozenInstanceError

import pytest

from mictlanix.cfdi.pac import MultifacturasSettings


def test_defaults() -> None:
    settings = MultifacturasSettings(user='USER', password='PASSWORD', production=True)
    assert settings.base_url == 'https://ws.multifacturas.com'
    assert settings.connect_timeout == 10.0
    assert settings.read_timeout == 60.0


def test_frozen_and_keyword_only() -> None:
    settings = MultifacturasSettings(user='USER', password='PASSWORD', production=False)
    with pytest.raises(FrozenInstanceError):
        settings.password = 'x'  # type: ignore[misc]
    with pytest.raises(TypeError):
        MultifacturasSettings('USER', 'PASSWORD', False)  # type: ignore[misc]


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('base_url', 'http://ws.multifacturas.com'),
        ('base_url', 'ws.multifacturas.com'),
        ('connect_timeout', 0.0),
        ('read_timeout', -1.0),
    ],
)
def test_invalid_values_are_refused_naming_the_field(field: str, value: object) -> None:
    with pytest.raises(ValueError, match=field):
        MultifacturasSettings(user='U', password='P', production=False, **{field: value})  # type: ignore[arg-type]


def test_repr_hides_the_password() -> None:
    settings = MultifacturasSettings(user='USER', password='s3cr3t!', production=False)
    assert 's3cr3t!' not in repr(settings)
    assert 'password=<hidden>' in repr(settings)
    assert "user='USER'" in repr(settings)
