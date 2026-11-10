"""
Skillora Desktop Client Non-Blocking Network Worker & UI Queue Dispatcher (client/network/socket_client.py)

Features:
- Dedicated background daemon worker thread using select.select() for non-blocking I/O multiplexing.
- Thread-safe request queue (queue.Queue) with automatic UUID request_id generation.
- Re-entrant thread-safe callback registry mapping request_id to UI response handlers.
- Response queue integrated with Tkinter's root.after(20, poll) main-thread polling loop.
- Fault-tolerant connection manager: auto-reconnect backoff, in-flight failover, and status observers.
- 100% standard library compliance: strictly zero third-party HTTP/web frameworks.
"""

import errno
import json
import logging
import queue
import select
import socket
import struct
import threading
import time
import uuid
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Tuple

from common.protocol import (
    HEADER_FORMAT,
    HEADER_SIZE,
    MAX_PAYLOAD_SIZE,
    decode_packet,
    encode_packet,
)

logger = logging.getLogger("skillora.socket_client")

DEFAULT_TIMEOUT = 15.0  # Default per-request timeout in seconds


@dataclass
class CallbackEntry:
    request_id: str
    action: str
    callback: Optional[Callable[[dict], None]]
    error_callback: Optional[Callable[[Any], None]]
    created_at: float
    timeout: float


class SocketClient:
    """
    Non-blocking raw TCP socket client designed for seamless Tkinter GUI integration.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 9999,
        auto_reconnect: bool = True,
        reconnect_interval: float = 2.0,
        default_timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self._host = host
        self._port = port
        self._auto_reconnect = auto_reconnect
        self._reconnect_interval = reconnect_interval
        self._default_timeout = default_timeout

        # Socket and lifecycle state
        self._sock: Optional[socket.socket] = None
        self._sock_lock = threading.Lock()
        self._connected = False
        self._connection_state = "DISCONNECTED"  # DISCONNECTED, CONNECTING, CONNECTED, RECONNECTING

        # Thread-safe queues
        self._request_queue: queue.Queue[dict] = queue.Queue()
        self._response_queue: queue.Queue[Tuple[str, Any]] = queue.Queue()

        # Callback registry with dedicated synchronization lock
        self._callback_registry: Dict[str, CallbackEntry] = {}
        self._registry_lock = threading.Lock()

        # Observers for connection state changes (e.g. status bar updates)
        self._status_listeners: List[Callable[[str, dict], None]] = []
        self._status_lock = threading.Lock()

        # Worker thread lifecycle controls
        self._stop_event = threading.Event()
        self._reconnect_event = threading.Event()
        self._worker_thread: Optional[threading.Thread] = None

        # In-memory stream accumulator buffer
        self._recv_buffer = bytearray()

        # Tkinter polling reference
        self._tk_root: Any = None
        self._tk_poll_after_id: Any = None
        self._tk_poll_interval_ms: int = 20

    # --------------------------------------------------------------------------
    # Lifecycle Management
    # --------------------------------------------------------------------------

    def start(self) -> None:
        """Starts the background worker thread."""
        if self._worker_thread is not None and self._worker_thread.is_alive():
            logger.warning("SocketClient background worker is already running.")
            return

        self._stop_event.clear()
        self._worker_thread = threading.Thread(
            target=self._worker_loop,
            name="Skillora-SocketClientWorker",
            daemon=True,
        )
        self._worker_thread.start()
        logger.info("SocketClient worker thread started, targeting %s:%d", self._host, self._port)

    def stop(self, timeout: float = 1.5) -> None:
        """
        Gracefully halts the background worker thread, closes the TCP socket,
        and unregisters any Tkinter polling timers.
        """
        logger.info("Stopping SocketClient...")
        self._stop_event.set()

        # Cancel Tkinter polling loop if registered
        if self._tk_root is not None and self._tk_poll_after_id is not None:
            try:
                self._tk_root.after_cancel(self._tk_poll_after_id)
            except Exception as ex:
                logger.debug("Failed to cancel Tk after callback: %s", ex)
            self._tk_poll_after_id = None

        # Close socket to wake up any pending select calls
        self._close_socket()

        # Wait for worker thread to exit
        if self._worker_thread is not None and self._worker_thread.is_alive():
            self._worker_thread.join(timeout=timeout)
            if self._worker_thread.is_alive():
                logger.warning("Worker thread did not terminate within %0.1fs timeout", timeout)
            self._worker_thread = None

        # Fail any remaining in-flight requests
        self._fail_all_pending_callbacks(
            code="CLIENT_STOPPED",
            message="Client was stopped before request could complete",
        )

        self._set_state("DISCONNECTED", {"reason": "Client stopped"})
        logger.info("SocketClient stopped successfully.")

    def reconnect_now(self) -> None:
        """
        Forces an immediate reconnection attempt.
        Starts the worker if not alive, or immediately interrupts backoff sleep.
        """
        logger.info("Manual reconnect requested.")
        if self._worker_thread is None or not self._worker_thread.is_alive():
            self.start()
        else:
            self._reconnect_event.set()

    def is_connected(self) -> bool:
        """Returns True if the client has an active, confirmed TCP connection."""
        return self._connected and (self._sock is not None)

    @property
    def connection_state(self) -> str:
        """Returns the current connection state string."""
        return self._connection_state

    # --------------------------------------------------------------------------
    # Request Dispatching (Called from GUI / Main Thread)
    # --------------------------------------------------------------------------

    def send_request(
        self,
        action: str,
        payload: Optional[dict] = None,
        callback: Optional[Callable[[dict], None]] = None,
        error_callback: Optional[Callable[[Any], None]] = None,
        timeout: Optional[float] = None,
    ) -> str:
        """
        Thread-safe method called from GUI views. Enqueues an outgoing request packet.
        Generates a unique request_id and registers the associated UI response callbacks.

        Returns the generated request_id string.
        """
        if not action or not isinstance(action, str):
            raise ValueError("Action must be a non-empty string.")

        request_id = f"req_{uuid.uuid4().hex}"
        eff_timeout = float(timeout) if timeout is not None else self._default_timeout
        now = time.time()

        # Register callback
        entry = CallbackEntry(
            request_id=request_id,
            action=action,
            callback=callback,
            error_callback=error_callback,
            created_at=now,
            timeout=eff_timeout,
        )
        with self._registry_lock:
            self._callback_registry[request_id] = entry

        # Construct standard wire request packet
        packet = {
            "action": action,
            "request_id": request_id,
            "payload": payload if payload is not None else {},
        }

        # Enqueue packet for background transmission
        self._request_queue.put(packet)
        logger.debug("Enqueued request %s (%s)", action, request_id)
        return request_id

    def send_request_sync(
        self,
        action: str,
        payload: Optional[dict] = None,
        timeout: float = 5.0,
    ) -> dict:
        """
        Synchronous request helper designed for automated tests and headless scripts.
        Blocks until the response arrives or the timeout expires.
        """
        response_holder: List[dict] = []
        error_holder: List[Any] = []
        done_event = threading.Event()

        def _on_success(res: dict) -> None:
            response_holder.append(res)
            done_event.set()

        def _on_error(err: Any) -> None:
            error_holder.append(err)
            done_event.set()

        self.send_request(
            action=action,
            payload=payload,
            callback=_on_success,
            error_callback=_on_error,
            timeout=timeout,
        )

        start_time = time.time()
        while not done_event.is_set():
            if time.time() - start_time > timeout:
                raise TimeoutError(f"Synchronous request {action} timed out after {timeout}s")
            # Poll responses manually so callbacks fire even without Tkinter after()
            self.poll_responses()
            time.sleep(0.01)

        if response_holder:
            return response_holder[0]
        if error_holder:
            return {"status": "ERROR", "error": error_holder[0]}
        raise RuntimeError("No response or error was captured")

    # --------------------------------------------------------------------------
    # Main-Thread Response Polling & Tkinter Integration
    # --------------------------------------------------------------------------

    def bind_to_tk(self, root: Any, interval_ms: int = 20) -> None:
        """
        Attaches the client polling routine to a Tkinter/CustomTkinter root window.
        Schedules continuous execution via root.after(interval_ms, ...).
        """
        self._tk_root = root
        self._tk_poll_interval_ms = interval_ms
        self._schedule_next_tk_poll()
        logger.info("SocketClient polling attached to Tkinter root (interval: %dms)", interval_ms)

    def _schedule_next_tk_poll(self) -> None:
        """Internal helper scheduling the next Tkinter timer tick."""
        if self._stop_event.is_set() or self._tk_root is None:
            return
        try:
            self._tk_poll_after_id = self._tk_root.after(
                self._tk_poll_interval_ms,
                self._on_tk_poll_tick,
            )
        except Exception as ex:
            logger.debug("Failed to schedule Tkinter after tick: %s", ex)

    def _on_tk_poll_tick(self) -> None:
        """Callback executed on Tkinter main thread by root.after()."""
        try:
            self.poll_responses()
        except Exception as ex:
            logger.exception("Unexpected error in poll_responses tick: %s", ex)
        finally:
            self._schedule_next_tk_poll()

    def poll_responses(self, max_items_per_poll: int = 50) -> int:
        """
        Drains up to max_items_per_poll items from response_queue and invokes
        registered UI callbacks on the main thread.
        Also sweeps expired requests.
        """
        processed_count = 0

        while processed_count < max_items_per_poll:
            try:
                item = self._response_queue.get_nowait()
            except queue.Empty:
                break

            processed_count += 1
            self._dispatch_queued_item(item)

        # Sweep callbacks whose timeouts have elapsed
        self._sweep_timeouts()
        return processed_count

    def _dispatch_queued_item(self, item: Any) -> None:
        """Dispatches a single item popped from response_queue on the main thread."""
        if isinstance(item, tuple) and len(item) == 2:
            event_type, data = item
        elif isinstance(item, dict):
            event_type, data = "RESPONSE", item
        else:
            logger.warning("Unrecognized item type in response_queue: %r", item)
            return

        if event_type == "SYS_STATUS":
            status_name = data.get("status", "UNKNOWN")
            self._notify_status_listeners(status_name, data)

        elif event_type == "RESPONSE":
            self._handle_response_packet(data)

        elif event_type == "FAIL_ENTRY":
            entry, err_packet = data
            error_data = err_packet.get("error")
            if entry.error_callback:
                try:
                    entry.error_callback(error_data)
                except Exception as ex:
                    logger.exception("Exception in UI error callback: %s", ex)
            elif entry.callback:
                try:
                    entry.callback(err_packet)
                except Exception as ex:
                    logger.exception("Exception in UI fallback callback: %s", ex)

    def _handle_response_packet(self, packet: dict) -> None:
        """Correlates a response packet with its callback and executes it."""
        request_id = packet.get("request_id")
        if not request_id:
            logger.warning("Received packet without request_id: %r", packet)
            return

        with self._registry_lock:
            entry = self._callback_registry.pop(request_id, None)

        if entry is None:
            logger.debug("Received response for untracked or expired request_id: %s", request_id)
            return

        status = packet.get("status", "SUCCESS")
        if status == "SUCCESS":
            if entry.callback:
                try:
                    entry.callback(packet)
                except Exception as ex:
                    logger.exception("Exception in UI success callback for %s: %s", request_id, ex)
        else:
            error_data = packet.get("error") or {"code": "UNKNOWN_ERROR", "message": "Unknown server error"}
            if entry.error_callback:
                try:
                    entry.error_callback(error_data)
                except Exception as ex:
                    logger.exception("Exception in UI error callback for %s: %s", request_id, ex)
            elif entry.callback:
                try:
                    entry.callback(packet)
                except Exception as ex:
                    logger.exception("Exception in UI fallback callback for %s: %s", request_id, ex)

    def _sweep_timeouts(self) -> None:
        """Identifies and fails any callbacks whose timeouts have elapsed."""
        now = time.time()
        expired: List[CallbackEntry] = []

        with self._registry_lock:
            for req_id, entry in list(self._callback_registry.items()):
                if now - entry.created_at > entry.timeout:
                    expired.append(self._callback_registry.pop(req_id))

        for entry in expired:
            logger.warning("Request %s (%s) timed out after %0.1fs", entry.action, entry.request_id, entry.timeout)
            timeout_packet = {
                "action": entry.action,
                "request_id": entry.request_id,
                "status": "ERROR",
                "payload": None,
                "error": {
                    "code": "REQUEST_TIMEOUT",
                    "message": f"Request {entry.action} timed out after {entry.timeout:.1f}s",
                },
            }
            if entry.error_callback:
                try:
                    entry.error_callback(timeout_packet["error"])
                except Exception as ex:
                    logger.exception("Error in timeout error_callback for %s: %s", entry.request_id, ex)
            elif entry.callback:
                try:
                    entry.callback(timeout_packet)
                except Exception as ex:
                    logger.exception("Error in timeout fallback callback for %s: %s", entry.request_id, ex)

    # --------------------------------------------------------------------------
    # Status Listeners & Observers
    # --------------------------------------------------------------------------

    def register_status_listener(self, listener: Callable[[str, dict], None]) -> None:
        """Registers a listener callback for connection state changes."""
        with self._status_lock:
            if listener not in self._status_listeners:
                self._status_listeners.append(listener)
        # Immediately notify of current state
        try:
            listener(self._connection_state, {"host": self._host, "port": self._port})
        except Exception as ex:
            logger.debug("Error delivering initial state to listener: %s", ex)

    def unregister_status_listener(self, listener: Callable[[str, dict], None]) -> None:
        """Removes a registered connection status listener."""
        with self._status_lock:
            if listener in self._status_listeners:
                self._status_listeners.remove(listener)

    def _set_state(self, state: str, extra: Optional[dict] = None) -> None:
        """Sets connection state and queues a system event for the main thread."""
        self._connection_state = state
        self._connected = (state == "CONNECTED")
        payload = {"status": state, "host": self._host, "port": self._port}
        if extra:
            payload.update(extra)
        self._response_queue.put(("SYS_STATUS", payload))

    def _notify_status_listeners(self, status: str, data: dict) -> None:
        """Invokes status listeners on the main thread."""
        with self._status_lock:
            listeners = list(self._status_listeners)
        for listener in listeners:
            try:
                listener(status, data)
            except Exception as ex:
                logger.exception("Error in connection status listener: %s", ex)

    # --------------------------------------------------------------------------
    # Background Worker Loop (Executes Exclusively on Daemon Thread)
    # --------------------------------------------------------------------------

    def _worker_loop(self) -> None:
        """Main loop executed by the background network worker thread."""
        logger.info("Background network worker loop entered.")

        while not self._stop_event.is_set():
            if not self._connected:
                self._attempt_connection()
                if not self._connected:
                    self._interruptible_sleep(self._reconnect_interval)
                    if not self._auto_reconnect:
                        logger.info("Auto-reconnect disabled; worker thread stopping.")
                        break
                    continue

            try:
                self._service_connected_socket()
            except OSError as ex:
                logger.warning("Socket error in service loop: %s", ex)
                self._handle_socket_disconnect(f"Socket error: {ex}")
            except Exception as ex:
                logger.exception("Unexpected error in worker loop: %s", ex)
                self._handle_socket_disconnect(f"Unexpected worker error: {ex}")

        logger.info("Background network worker loop exiting cleanly.")

    def _attempt_connection(self) -> None:
        """Attempts to establish a TCP socket connection to the server."""
        self._set_state("CONNECTING" if self._connection_state == "DISCONNECTED" else "RECONNECTING")
        self._close_socket()

        sock = None
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1.0)
            with self._sock_lock:
                self._sock = sock
            sock.connect((self._host, self._port))
            sock.settimeout(2.0)

            with self._sock_lock:
                self._recv_buffer.clear()

            self._set_state("CONNECTED")
            logger.info("Successfully connected to Skillora server at %s:%d", self._host, self._port)

        except (ConnectionRefusedError, socket.timeout, OSError) as ex:
            logger.debug("Connection attempt to %s:%d failed: %s", self._host, self._port, ex)
            self._close_socket()
            self._set_state("DISCONNECTED", {"error": str(ex)})

    def _service_connected_socket(self) -> None:
        """
        Executes one service iteration:
        1. Transmits pending outgoing packets from request_queue.
        2. Monitors socket readability via select.select(..., timeout=0.02).
        3. Accumulates bytes and unpacks length-prefixed frames.
        """
        current_sock = self._sock
        if current_sock is None:
            return

        # 1. Drain and transmit outgoing requests
        while not self._request_queue.empty() and not self._stop_event.is_set():
            try:
                req_packet = self._request_queue.get_nowait()
            except queue.Empty:
                break

            try:
                encoded_bytes = self._encode_frame(req_packet)
                current_sock.sendall(encoded_bytes)
                logger.debug("Transmitted packet: %s (%s)", req_packet.get("action"), req_packet.get("request_id"))
            except OSError as ex:
                logger.warning("Failed to transmit packet: %s", ex)
                self._handle_socket_disconnect(f"Send failed: {ex}")
                return

        # 2. Check for incoming data via select.select with 20ms timeout
        try:
            readable, _, _ = select.select([current_sock], [], [], 0.02)
        except (ValueError, OSError) as ex:
            logger.debug("Select error (socket closed?): %s", ex)
            return

        if readable:
            try:
                chunk = current_sock.recv(4096)
            except (BlockingIOError, InterruptedError):
                return
            except socket.timeout:
                return
            except OSError as ex:
                self._handle_socket_disconnect(f"Recv error: {ex}")
                return

            if not chunk:
                # Clean EOF received from peer
                logger.info("Server closed the connection (EOF received).")
                self._handle_socket_disconnect("Server closed connection")
                return

            # 3. Accumulate and unpack frames
            self._recv_buffer.extend(chunk)
            self._process_recv_buffer()

    def _process_recv_buffer(self) -> None:
        """Decodes complete length-prefixed packets from the in-memory buffer."""
        while len(self._recv_buffer) >= HEADER_SIZE:
            try:
                packet, remainder = decode_packet(bytes(self._recv_buffer))
            except Exception as ex:
                logger.error("Failed to decode packet from buffer: %s", ex)
                self._recv_buffer.clear()
                self._handle_socket_disconnect("Corrupted frame length or JSON")
                return

            if packet is None:
                # Incomplete frame; wait for next recv
                break

            self._recv_buffer = bytearray(remainder)
            self._response_queue.put(("RESPONSE", packet))

    def _handle_socket_disconnect(self, reason: str) -> None:
        """Handles unexpected socket disconnection and triggers failover."""
        logger.warning("Handling socket disconnection: %s", reason)
        self._close_socket()
        self._set_state("RECONNECTING" if self._auto_reconnect else "DISCONNECTED", {"reason": reason})

        # Fail all currently in-flight requests
        self._fail_all_pending_callbacks(
            code="CONNECTION_LOST",
            message=f"Connection lost while request was in-flight ({reason})",
        )

    def _fail_all_pending_callbacks(self, code: str, message: str) -> None:
        """Generates synthetic error responses for all pending callbacks in the registry."""
        with self._registry_lock:
            pending_entries = list(self._callback_registry.values())
            self._callback_registry.clear()

        for entry in pending_entries:
            err_packet = {
                "action": entry.action,
                "request_id": entry.request_id,
                "status": "ERROR",
                "payload": None,
                "error": {"code": code, "message": message},
            }
            self._response_queue.put(("FAIL_ENTRY", (entry, err_packet)))

    def _close_socket(self) -> None:
        """Thread-safely shuts down and closes the TCP socket."""
        with self._sock_lock:
            if self._sock is not None:
                try:
                    self._sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    self._sock.close()
                except OSError:
                    pass
                self._sock = None
            self._connected = False

    def _interruptible_sleep(self, seconds: float) -> None:
        """Sleeps in 50ms intervals while checking for stop_event or explicit reconnect request."""
        end_time = time.time() + seconds
        while time.time() < end_time and not self._stop_event.is_set():
            if self._reconnect_event.is_set():
                self._reconnect_event.clear()
                break
            time.sleep(0.05)

    @staticmethod
    def _encode_frame(data: dict) -> bytes:
        """Serializes dictionary to 4-byte big-endian length-prefixed UTF-8 JSON bytes."""
        return encode_packet(data)
