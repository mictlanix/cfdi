"""The errors a SAT status client raises. Callers branch on the type and on ``SatRejected.code``."""

from __future__ import annotations

from mictlanix.cfdi._errors import CfdiError


class SatError(CfdiError):
    """Base of everything a SAT status client raises."""


class SatRejected(SatError):
    """The SAT's answer could not be read, or the service refused the request."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f'{code}: {message}')
        self.code = code
        self.message = message


class SatUnavailable(SatError):
    """The request did not reach the SAT; retrying is safe."""

    def __init__(self) -> None:
        super().__init__('the SAT could not be reached; nothing was asked')


class SatTimeout(SatError):
    """The request reached the SAT and no usable answer came in time; asking again is safe."""

    def __init__(self) -> None:
        super().__init__('the SAT did not answer in time')
