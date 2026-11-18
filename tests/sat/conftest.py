"""Fixtures for the SAT tests: replayed SAT answers, and the simulated PAC's fixtures."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pytest
from lxml import etree

from tests.pac.conftest import (  # noqa: F401  (fixtures for the simulated client)
    clock,
    credentials,
    make_sealed,
)

SAT = Path(__file__).resolve().parent.parent / 'fixtures' / 'sat'


@dataclass
class Sent:
    """One request a client sent through the replayed transport."""

    url: str
    action: str
    expression: str
    timeouts: Any


class Replay:
    """Answers each ``_soap._post`` from a queue of fixture names, raw answers or exceptions."""

    def __init__(self) -> None:
        self.answers: list[str | bytes | BaseException] = []
        self.sent: list[Sent] = []

    def __call__(self, *answers: str | bytes | BaseException) -> list[Sent]:
        self.answers.extend(answers)
        return self.sent

    def post(self, url: str, action: str, body: bytes, timeouts: Any) -> bytes:
        expression = next(
            node.text or ''
            for node in etree.fromstring(body).iter()
            if isinstance(node.tag, str) and etree.QName(node).localname == 'expresionImpresa'
        )
        self.sent.append(Sent(url, action, expression, timeouts))
        assert self.answers, f'no answer queued for {action}'
        answer = self.answers.pop(0)
        if isinstance(answer, BaseException):
            raise answer
        if isinstance(answer, bytes):
            return answer
        return (SAT / answer).read_bytes()


@pytest.fixture
def replay(monkeypatch: pytest.MonkeyPatch) -> Replay:
    from mictlanix.cfdi import _soap

    fake = Replay()
    monkeypatch.setattr(_soap, '_post', fake.post)
    return fake
