import socket

import pytest


def test_opening_a_connection_raises() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(RuntimeError, match='must not use the network'):
            sock.connect(('192.0.2.1', 443))


def test_connect_ex_raises() -> None:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        with pytest.raises(RuntimeError, match='must not use the network'):
            sock.connect_ex(('192.0.2.1', 443))
