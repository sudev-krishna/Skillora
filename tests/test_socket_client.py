#!/usr/bin/env python3
"""
Unit and integration test suite for SocketClient (client/network/socket_client.py).
Tests start/stop lifecycle, request queueing, UUID generation, round-trip communication,
concurrent request correlation, sync request helper, offline refusal, timeout sweeper,
in-flight failover, chunked stream accumulation, auto-reconnect, and Tkinter polling safety.
"""

import re
import socket
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.network.socket_client import SocketClient
from common.protocol import (
    MAX_PAYLOAD_SIZE,
    create_request,
    create_response,
    decode_packet,
    encode_packet,
    receive_packet,
    send_packet,
)
from server.network.dispatcher import ActionDispatcher
from server.network.tcp_server import SkilloraServer


class MockTkRoot:
    """Mock Tkinter root object for testing bind_to_tk without GUI display."""

    def __init__(self):
        self.timers: Dict[int, Any] = {}
        self._timer_counter = 0

    def after(self, ms: int, func: Any) -> int:
        self._timer_counter += 1
        timer_id = self._timer_counter
        self.timers[timer_id] = (ms, func)
        return timer_id

    def after_cancel(self, timer_id: int) -> None:
        self.timers.pop(timer_id, None)


class TestSocketClient(unittest.TestCase):
    """Tests for SocketClient."""

    def test_client_start_stop_clean(self):
        """Starts client, verifies daemon worker is alive, stops and joins cleanly."""
        client = SocketClient(host="127.0.0.1", port=59999, auto_reconnect=False)
        self.assertFalse(client.is_connected())

        client.start()
        self.assertIsNotNone(client._worker_thread)
        self.assertTrue(client._worker_thread.is_alive())
        self.assertTrue(client._worker_thread.daemon)

        start_stop = time.time()
        client.stop(timeout=1.0)
        self.assertLess(time.time() - start_stop, 1.5)
        self.assertFalse(client.is_connected())
        self.assertIsNone(client._worker_thread)

    def test_request_envelope_formatting_and_uuid(self):
        """send_request enqueues well-formed request packet with UUID request_id."""
        client = SocketClient(host="127.0.0.1", port=59999, auto_reconnect=False)
        req_id = client.send_request("GET_COMPANIES", {"tier": 1})

        self.assertTrue(req_id.startswith("req_"))
        self.assertTrue(re.match(r"^req_[0-9a-f]{32}$", req_id))

        # Check item in queue
        item = client._request_queue.get_nowait()
        self.assertEqual(item["action"], "GET_COMPANIES")
        self.assertEqual(item["request_id"], req_id)
        self.assertEqual(item["payload"], {"tier": 1})

    def test_round_trip_request_response(self):
        """Client connects to server, sends request, and executes callback on poll_responses."""
        dispatcher = ActionDispatcher()

        @dispatcher.route("ECHO")
        def handle_echo(payload):
            return {"echo_payload": payload}

        with SkilloraServer(host="127.0.0.1", port=0, dispatcher=dispatcher) as server:
            client = SocketClient(host="127.0.0.1", port=server.port, auto_reconnect=False)
            client.start()

            # Wait for connection
            deadline = time.time() + 2.0
            while not client.is_connected() and time.time() < deadline:
                time.sleep(0.02)
            self.assertTrue(client.is_connected())

            results = []
            req_id = client.send_request("ECHO", {"msg": "Skillora"}, callback=lambda r: results.append(r))

            # Poll until response received
            poll_deadline = time.time() + 2.0
            while not results and time.time() < poll_deadline:
                client.poll_responses()
                time.sleep(0.01)

            self.assertEqual(len(results), 1)
            self.assertEqual(results[0]["action"], "ECHO")
            self.assertEqual(results[0]["request_id"], req_id)
            self.assertEqual(results[0]["status"], "SUCCESS")
            self.assertEqual(results[0]["payload"]["echo_payload"], {"msg": "Skillora"})

            client.stop()

    def test_multiple_concurrent_requests(self):
        """Multiple concurrent requests sent in rapid succession correlate to their callbacks."""
        dispatcher = ActionDispatcher()

        @dispatcher.route("SQUARE")
        def handle_square(payload):
            val = payload.get("val", 0)
            return {"result": val * val}

        with SkilloraServer(host="127.0.0.1", port=0, dispatcher=dispatcher) as server:
            client = SocketClient(host="127.0.0.1", port=server.port, auto_reconnect=False)
            client.start()

            deadline = time.time() + 2.0
            while not client.is_connected() and time.time() < deadline:
                time.sleep(0.02)

            received = {}
            for i in range(10):
                val = i + 1

                def make_cb(v):
                    return lambda res: received.update({v: res["payload"]["result"]})

                client.send_request("SQUARE", {"val": val}, callback=make_cb(val))

            poll_deadline = time.time() + 3.0
            while len(received) < 10 and time.time() < poll_deadline:
                client.poll_responses()
                time.sleep(0.02)

            self.assertEqual(len(received), 10)
            for i in range(10):
                val = i + 1
                self.assertEqual(received[val], val * val)

            client.stop()

    def test_sync_request_helper(self):
        """send_request_sync blocks and returns the exact response dictionary."""
        with SkilloraServer(host="127.0.0.1", port=0) as server:
            client = SocketClient(host="127.0.0.1", port=server.port, auto_reconnect=False)
            client.start()

            deadline = time.time() + 2.0
            while not client.is_connected() and time.time() < deadline:
                time.sleep(0.02)

            res = client.send_request_sync("PING", {"test_key": 42}, timeout=3.0)
            self.assertEqual(res["status"], "SUCCESS")
            self.assertEqual(res["action"], "PING")
            self.assertIn("server_time", res["payload"])

            client.stop()

    def test_connection_refusal_startup(self):
        """Pointing client to offline server does not crash; state transitions to DISCONNECTED."""
        client = SocketClient(host="127.0.0.1", port=59998, auto_reconnect=False, reconnect_interval=0.1)
        client.start()

        deadline = time.time() + 3.0
        while client.connection_state == "CONNECTING" and time.time() < deadline:
            time.sleep(0.05)

        self.assertFalse(client.is_connected())
        self.assertEqual(client.connection_state, "DISCONNECTED")

        client.stop()

    def test_request_timeout_sweeper(self):
        """Requests exceeding their configured timeout trigger error callbacks with REQUEST_TIMEOUT."""
        # Use an unresponsive server that accepts connections but never responds
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        client = SocketClient(host="127.0.0.1", port=port, auto_reconnect=False)
        client.start()

        conn, _ = listener.accept()

        errors = []
        client.send_request(
            "HANG_TEST",
            {},
            error_callback=lambda err: errors.append(err),
            timeout=0.15,
        )

        time.sleep(0.25)
        client.poll_responses()

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "REQUEST_TIMEOUT")
        self.assertIn("timed out", errors[0]["message"])

        client.stop()
        conn.close()
        listener.close()

    def test_abrupt_disconnect_inflight_failover(self):
        """When server disconnects mid-flight, pending requests fail with CONNECTION_LOST."""
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]

        client = SocketClient(host="127.0.0.1", port=port, auto_reconnect=False)
        client.start()

        conn, _ = listener.accept()

        deadline = time.time() + 2.0
        while not client.is_connected() and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(client.is_connected())

        errors = []
        client.send_request(
            "INFLIGHT_ACTION",
            {},
            error_callback=lambda err: errors.append(err),
            timeout=5.0,
        )

        time.sleep(0.05)

        # Abruptly close server connection
        conn.close()
        listener.close()

        # Allow worker to detect EOF
        deadline = time.time() + 2.0
        while not errors and time.time() < deadline:
            client.poll_responses()
            time.sleep(0.02)

        self.assertEqual(len(errors), 1)
        self.assertEqual(errors[0]["code"], "CONNECTION_LOST")

        client.stop()

    def test_oversized_packet_rejection(self):
        """Attempting to encode a packet > 16 MB raises ValueError before transmission."""
        client = SocketClient(host="127.0.0.1", port=59999)
        oversized_data = {"key": "X" * (MAX_PAYLOAD_SIZE + 10)}
        with self.assertRaises(ValueError):
            client._encode_frame(oversized_data)

    def test_chunked_stream_accumulation(self):
        """_process_recv_buffer decodes packet only when all chunk fragments have arrived."""
        client = SocketClient(host="127.0.0.1", port=59999)
        test_packet = {"action": "PING", "request_id": "req-chunk-1", "payload": {"foo": "bar"}}
        encoded = encode_packet(test_packet)

        # Feed byte-by-byte into client._recv_buffer and test accumulation
        for byte_idx in range(len(encoded) - 1):
            client._recv_buffer.extend(encoded[byte_idx:byte_idx + 1])
            client._process_recv_buffer()
            # Queue should still be empty
            self.assertTrue(client._response_queue.empty())

        # Feed the final remaining byte
        client._recv_buffer.extend(encoded[-1:])
        client._process_recv_buffer()

        self.assertFalse(client._response_queue.empty())
        item = client._response_queue.get_nowait()
        self.assertEqual(item[0], "RESPONSE")
        self.assertEqual(item[1]["request_id"], "req-chunk-1")

    def test_auto_reconnect_lifecycle(self):
        """Client in auto-reconnect mode automatically reconnects when server restarts."""
        server = SkilloraServer(host="127.0.0.1", port=0)
        server.start(blocking=False)
        port = server.port

        status_events = []
        client = SocketClient(
            host="127.0.0.1",
            port=port,
            auto_reconnect=True,
            reconnect_interval=0.1,
        )
        client.register_status_listener(lambda s, d: status_events.append(s))
        client.start()

        # Wait for connected
        deadline = time.time() + 2.0
        while not client.is_connected() and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(client.is_connected())

        # Stop server
        server.stop()
        time.sleep(0.15)
        client.poll_responses()
        self.assertIn("RECONNECTING", status_events)

        # Restart server on same port
        server2 = SkilloraServer(host="127.0.0.1", port=port)
        server2.start(blocking=False)

        # Wait for reconnected
        reconnect_deadline = time.time() + 2.0
        while not client.is_connected() and time.time() < reconnect_deadline:
            time.sleep(0.05)
        client.poll_responses()

        self.assertTrue(client.is_connected())
        self.assertEqual(status_events[-1], "CONNECTED")

        client.stop()
        server2.stop()

    def test_tkinter_main_thread_callback_safety(self):
        """Callbacks registered with bind_to_tk execute on the thread calling poll_responses."""
        with SkilloraServer(host="127.0.0.1", port=0) as server:
            client = SocketClient(host="127.0.0.1", port=server.port, auto_reconnect=False)
            mock_tk = MockTkRoot()
            client.bind_to_tk(mock_tk, interval_ms=10)
            client.start()

            deadline = time.time() + 2.0
            while not client.is_connected() and time.time() < deadline:
                time.sleep(0.02)

            main_thread_id = threading.get_ident()
            callback_thread_id = []

            def record_thread(res):
                callback_thread_id.append(threading.get_ident())

            client.send_request("PING", callback=record_thread)

            poll_deadline = time.time() + 2.0
            while not callback_thread_id and time.time() < poll_deadline:
                # Simulate Tkinter timer execution on main thread
                client._on_tk_poll_tick()
                time.sleep(0.02)

            self.assertEqual(len(callback_thread_id), 1)
            self.assertEqual(callback_thread_id[0], main_thread_id)

            client.stop()

    def test_real_world_placement_workload(self):
        """Simulates full multi-step placement preparation workflow across a single connection."""
        dispatcher = ActionDispatcher()

        @dispatcher.route("AUTH_LOGIN")
        def handle_auth(p):
            return {"user_id": 101, "name": "Rahul Sharma", "cgpa": 8.5}

        @dispatcher.route("GET_COMPANIES")
        def handle_companies(p):
            return {"companies": ["Amazon", "Zoho", "TCS", "Infosys"]}

        @dispatcher.route("CHECK_ELIGIBILITY")
        def handle_eligibility(p):
            return {"eligible": True, "tier": "Tier 1 Product"}

        @dispatcher.route("SOLVE_RECURRENCE")
        def handle_solve(p):
            return {"equation": p.get("eq"), "big_o": "O(N log N)", "closed_form": "N*log2(N)"}

        @dispatcher.route("EXECUTE_CODE_SANDBOX")
        def handle_sandbox(p):
            return {"runtime_sec": 0.042, "divergence": False}

        with SkilloraServer(host="127.0.0.1", port=0, dispatcher=dispatcher) as server:
            client = SocketClient(host="127.0.0.1", port=server.port, auto_reconnect=False)
            client.start()

            deadline = time.time() + 2.0
            while not client.is_connected() and time.time() < deadline:
                time.sleep(0.02)

            auth_res = client.send_request_sync("AUTH_LOGIN", {"username": "rahul", "password": "xyz"})
            self.assertEqual(auth_res["status"], "SUCCESS")
            self.assertEqual(auth_res["payload"]["user_id"], 101)

            comp_res = client.send_request_sync("GET_COMPANIES", {})
            self.assertEqual(len(comp_res["payload"]["companies"]), 4)

            elig_res = client.send_request_sync("CHECK_ELIGIBILITY", {"cgpa": 8.5})
            self.assertTrue(elig_res["payload"]["eligible"])

            math_res = client.send_request_sync("SOLVE_RECURRENCE", {"eq": "T(n)=2T(n/2)+n"})
            self.assertEqual(math_res["payload"]["big_o"], "O(N log N)")

            code_res = client.send_request_sync("EXECUTE_CODE_SANDBOX", {"code": "def solution(): pass"})
            self.assertFalse(code_res["payload"]["divergence"])

            client.stop()


if __name__ == "__main__":
    unittest.main()
