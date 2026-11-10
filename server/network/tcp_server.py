"""
Skillora Server Multi-Client TCP Socket Server (server/network/tcp_server.py)
Implements multi-client concurrent worker threads, non-blocking accept loops, and clean shutdown.
Strictly zero third-party web frameworks (standard library only).
"""

import logging
import socket
import threading
import time
from typing import Any, Dict, List, Optional, Set, Tuple

from common.protocol import (
    FrameSizeExceededError,
    IncompleteFrameError,
    MalformedJSONError,
    ProtocolError,
    encode_packet,
    receive_packet,
)
from server.network.dispatcher import ActionDispatcher

logger = logging.getLogger("skillora.tcp_server")


class ClientHandlerThread(threading.Thread):
    """Worker daemon thread servicing a single connected client socket."""

    def __init__(
        self,
        client_socket: socket.socket,
        client_address: Tuple[str, int],
        dispatcher: ActionDispatcher,
        server: Optional["SkilloraServer"] = None,
        stop_event: Optional[threading.Event] = None,
    ) -> None:
        super().__init__(name=f"ClientHandler-{client_address[0]}:{client_address[1]}")
        self.client_socket = client_socket
        self.client_address = client_address
        self.dispatcher = dispatcher
        self.server = server
        self.stop_event = stop_event or threading.Event()
        self._local_stop = threading.Event()
        self._send_lock = threading.Lock()
        self.daemon = True

    def run(self) -> None:
        logger.info(f"Client connected from {self.client_address}")
        try:
            while not self.stop_event.is_set() and not self._local_stop.is_set():
                try:
                    packet = receive_packet(self.client_socket)
                except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                    logger.debug(f"Client {self.client_address} reset connection")
                    break
                except (FrameSizeExceededError, IncompleteFrameError, MalformedJSONError, ProtocolError, ValueError) as pe:
                    logger.warning(f"Protocol error from {self.client_address}: {pe}")
                    err_response = {
                        "action": "ERROR",
                        "request_id": "",
                        "status": "ERROR",
                        "payload": None,
                        "error": str(pe),
                    }
                    try:
                        self.send_packet(err_response)
                    except Exception:
                        pass
                    break
                except OSError:
                    # Socket closed by server shutdown or local close
                    break

                if packet is None:
                    # Clean EOF from peer at message boundary
                    logger.debug(f"Client {self.client_address} disconnected cleanly (EOF)")
                    break

                # Dispatch request to registered business logic
                response = self.dispatcher.dispatch(packet)

                # Send response back to client
                self.send_packet(response)

        except Exception as exc:
            logger.exception(f"Unexpected exception in ClientHandlerThread {self.client_address}: {exc}")
        finally:
            self._cleanup()

    def send_packet(self, data: Dict[str, Any]) -> None:
        """Encode and send a packet over the client socket safely."""
        raw_bytes = encode_packet(data)
        with self._send_lock:
            self.client_socket.sendall(raw_bytes)

    def stop(self) -> None:
        """Interrupt and close the client socket."""
        self._local_stop.set()
        try:
            self.client_socket.shutdown(socket.SHUT_RDWR)
        except Exception:
            pass
        try:
            self.client_socket.close()
        except Exception:
            pass

    def _cleanup(self) -> None:
        """Ensure socket is closed and thread is unregistered from server."""
        try:
            self.client_socket.close()
        except Exception:
            pass
        if self.server is not None:
            self.server._unregister_client(self)
        logger.info(f"Client disconnected from {self.client_address}")


class SkilloraServer:
    """Multi-client raw TCP socket server."""

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9999,
        dispatcher: Optional[ActionDispatcher] = None,
        backlog: int = 128,
    ) -> None:
        self._host = host
        self._port = port
        self._bound_host: Optional[str] = None
        self._bound_port: Optional[int] = None
        self._backlog = backlog
        self.dispatcher = dispatcher if dispatcher is not None else ActionDispatcher()

        self._server_sock: Optional[socket.socket] = None
        self._listener_thread: Optional[threading.Thread] = None
        self._stop_event = threading.Event()
        self._started_event = threading.Event()
        self._running = False

        self._clients: Set[ClientHandlerThread] = set()
        self._clients_lock = threading.Lock()

    @property
    def host(self) -> str:
        """Return configured or bound host."""
        return self._bound_host if self._bound_host is not None else self._host

    @property
    def port(self) -> int:
        """Return configured or bound port. If port 0 was passed, returns actual allocated port."""
        return self._bound_port if self._bound_port is not None else self._port

    @property
    def is_running(self) -> bool:
        """Check if server is active and accepting connections."""
        return self._running and not self._stop_event.is_set()

    @property
    def active_clients_count(self) -> int:
        """Return count of currently connected clients."""
        with self._clients_lock:
            return len(self._clients)

    def start(self, blocking: bool = False) -> None:
        """
        Start the TCP socket server.
        If blocking=False, listener runs in a background daemon thread.
        """
        if self.is_running:
            logger.warning("SkilloraServer is already running")
            return

        self._stop_event.clear()
        self._started_event.clear()

        # 1. Create and bind TCP socket
        self._server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server_sock.bind((self._host, self._port))

        # 2. Record bound address (captures dynamic port if port=0 was specified)
        self._bound_host, self._bound_port = self._server_sock.getsockname()
        self._port = self._bound_port

        # 3. Begin listening with accept timeout
        self._server_sock.listen(self._backlog)
        self._server_sock.settimeout(0.5)
        self._running = True
        self._started_event.set()

        logger.info(f"SkilloraServer listening on {self._bound_host}:{self._bound_port} (backlog={self._backlog})")

        if blocking:
            self._listen_loop()
        else:
            self._listener_thread = threading.Thread(
                target=self._listen_loop,
                name=f"SkilloraServer-Listener-{self._bound_port}",
                daemon=True,
            )
            self._listener_thread.start()

    def serve_forever(self) -> None:
        """Block until stop() is called."""
        if not self.is_running:
            self.start(blocking=True)
        else:
            if self._listener_thread is not None:
                self._listener_thread.join()

    def _listen_loop(self) -> None:
        """Accept incoming client connections in a loop."""
        while not self._stop_event.is_set() and self._running:
            try:
                assert self._server_sock is not None
                client_sock, client_addr = self._server_sock.accept()
            except socket.timeout:
                continue
            except OSError:
                if self._stop_event.is_set():
                    break
                logger.debug("Socket accept failed while listening")
                break

            # Spawn dedicated worker daemon thread
            handler = ClientHandlerThread(
                client_socket=client_sock,
                client_address=client_addr,
                dispatcher=self.dispatcher,
                server=self,
                stop_event=self._stop_event,
            )
            self._register_client(handler)
            handler.start()

        self._running = False

    def _register_client(self, handler: ClientHandlerThread) -> None:
        with self._clients_lock:
            self._clients.add(handler)

    def _unregister_client(self, handler: ClientHandlerThread) -> None:
        with self._clients_lock:
            self._clients.discard(handler)

    def stop(self, timeout: float = 3.0) -> None:
        """Clean shutdown: stops listener, closes client sockets, and joins threads."""
        if not self._running and self._stop_event.is_set():
            return

        logger.info("Stopping SkilloraServer...")
        self._stop_event.set()
        self._running = False

        # 1. Close listening socket
        if self._server_sock is not None:
            try:
                self._server_sock.close()
            except Exception:
                pass
            self._server_sock = None

        # 2. Terminate all active clients
        with self._clients_lock:
            clients_snapshot = list(self._clients)

        for client in clients_snapshot:
            try:
                client.stop()
            except Exception:
                pass

        # 3. Join client threads
        deadline = time.time() + timeout
        for client in clients_snapshot:
            remaining = max(0.01, deadline - time.time())
            client.join(timeout=remaining)

        # 4. Join listener thread
        if self._listener_thread is not None and self._listener_thread.is_alive():
            remaining = max(0.01, deadline - time.time())
            self._listener_thread.join(timeout=remaining)
            self._listener_thread = None

        with self._clients_lock:
            self._clients.clear()

        logger.info("SkilloraServer stopped cleanly")

    def __enter__(self) -> "SkilloraServer":
        self.start(blocking=False)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.stop()
