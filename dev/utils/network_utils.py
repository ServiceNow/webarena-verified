"""Network utilities."""

import socket


def find_free_port() -> int:
    """Find and return an available TCP port.

    Uses the OS to allocate a free port by binding to port 0,
    which lets the OS choose an available port.
    """
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind(("", 0))
        return s.getsockname()[1]
