"""The errors a PAC client raises. Callers branch on the type and on ``PacRejected.code``."""

from __future__ import annotations

from mictlanix.cfdi._errors import CfdiError


class PacError(CfdiError):
    """Base of everything a PAC client operation raises."""


class PacRejected(PacError):
    """The PAC or the SAT refused the request; nothing was done."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f'{code}: {message}')
        self.code = code
        self.message = message


class PacUnavailable(PacError):
    """The request did not reach the PAC; nothing was done, and retrying is safe."""

    def __init__(self) -> None:
        super().__init__('the PAC could not be reached; nothing was done')


class PacTimeout(PacError):
    """The outcome is unknown; resolve it with ``find_stamp`` or ``query_status``."""

    def __init__(self) -> None:
        super().__init__('the PAC did not answer in time; the outcome is unknown')
