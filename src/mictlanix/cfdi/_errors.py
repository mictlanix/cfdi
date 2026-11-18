"""The library's errors and the violations validation reports.

Callers branch on the exception class, on ``CsdError.reason`` and on ``Violation.rule``; no
message text needs to be parsed. No error ever carries key material or a password.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


@dataclass(frozen=True)
class Violation:
    """One broken rule.

    ``node`` is an XPath with the SAT's prefixes, ``attribute`` the attribute concerned (if
    any), and ``rule`` an XSD constraint name, a SAT validation code or a library rule name.
    ``message`` is for people.
    """

    node: str
    attribute: str | None
    rule: str
    message: str


class CfdiError(Exception):
    """Base class of every error the library raises."""


class ValidationError(CfdiError):
    """A document breaks one or more rules."""

    def __init__(self, violations: Iterable[Violation]) -> None:
        self.violations = list(violations)
        summary = '; '.join(
            f'{v.rule} at {v.node}' + (f'/@{v.attribute}' if v.attribute else '')
            for v in self.violations
        )
        super().__init__(f'{len(self.violations)} violation(s): {summary}')


class CsdError(CfdiError):
    """The CSD's certificate or private key cannot be used."""

    class Reason(StrEnum):
        INVALID_CERTIFICATE = 'invalid_certificate'
        INVALID_KEY = 'invalid_key'
        WRONG_PASSWORD = 'wrong_password'
        KEY_MISMATCH = 'key_mismatch'

    def __init__(self, reason: Reason) -> None:
        self.reason = reason
        super().__init__(f'the CSD cannot be used: {reason.value}')


class CertificateValidityError(CfdiError):
    """The document's ``Fecha`` is outside the certificate's validity period."""

    def __init__(self, fecha: datetime, valid_from: datetime, valid_to: datetime) -> None:
        self.fecha = fecha
        self.valid_from = valid_from
        self.valid_to = valid_to
        super().__init__(
            f'Fecha {fecha.isoformat()} is outside the certificate validity '
            f'{valid_from.isoformat()} to {valid_to.isoformat()}'
        )


class ParseError(CfdiError):
    """The input cannot be read: XML that is not well-formed, or a value of the wrong type.

    For XML that is not well-formed, ``line`` and ``column`` give the position. For a value
    that cannot be turned into the models, ``node`` and ``attribute`` name it.
    """

    def __init__(
        self,
        message: str,
        *,
        line: int | None = None,
        column: int | None = None,
        node: str | None = None,
        attribute: str | None = None,
    ) -> None:
        self.line = line
        self.column = column
        self.node = node
        self.attribute = attribute
        super().__init__(message)


class NotCfdi40Error(CfdiError):
    """The input is XML but not a CFDI 4.0 ``Comprobante``."""

    def __init__(self, root: str, version: str | None) -> None:
        self.root = root
        self.version = version
        super().__init__(f'not a CFDI 4.0 Comprobante: root {root}, version {version}')


class NotStampedError(CfdiError):
    """The document carries no ``TimbreFiscalDigital``, or lacks data a stamp requires."""

    def __init__(self, message: str = 'the document is not stamped') -> None:
        super().__init__(message)
