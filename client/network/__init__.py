"""
Skillora Client Network Package
Non-blocking TCP socket client and Tkinter UI queue bridge.
Strictly zero third-party web frameworks (standard library only).
"""

from client.network.socket_client import CallbackEntry, SocketClient

__all__ = [
    "CallbackEntry",
    "SocketClient",
]
