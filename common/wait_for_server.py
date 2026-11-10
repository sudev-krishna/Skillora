"""
Skillora Socket Synchronizer (common/wait_for_server.py)
Awaits TCP server readiness on port 9999 before launching desktop GUI client.
Ensures zero race conditions between server binding and client connection.
"""

from __future__ import annotations

import socket
import sys
import time


def wait_for_server(
    host: str = "127.0.0.1",
    port: int = 9999,
    max_seconds: float = 6.0,
    poll_interval: float = 0.15,
) -> bool:
    """
    Polls the target host and port until a TCP connection succeeds or timeout expires.
    Returns True if connection succeeded, False otherwise.
    """
    deadline = time.time() + max_seconds
    while time.time() < deadline:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.2)
        try:
            res = s.connect_ex((host, port))
            s.close()
            if res == 0:
                return True
        except Exception:
            try:
                s.close()
            except Exception:
                pass
        time.sleep(poll_interval)
    return False


def main() -> int:
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9999
    host = sys.argv[2] if len(sys.argv) > 2 else "127.0.0.1"
    ready = wait_for_server(host=host, port=port, max_seconds=6.0)
    if ready:
        print(f"[*] Skillora Server online on {host}:{port}.")
        return 0
    else:
        print(f"[!] Server not detected on {host}:{port} within 6s timeout; launching client in fallback mode.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
