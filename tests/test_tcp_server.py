#!/usr/bin/env python3
"""
Unit and integration test suite for SkilloraServer (server/network/tcp_server.py).
Tests socket lifecycle, ephemeral port 0 binding, SO_REUSEADDR immediate rebinding,
multi-client concurrency, failure isolation, client count tracking, and clean shutdown.
"""

import socket
import struct
import sys
import threading
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from common.protocol import (
    create_request,
    decode_packet,
    encode_packet,
    receive_packet,
    send_packet,
)
from server.network.dispatcher import ActionDispatcher
from server.network.tcp_server import SkilloraServer


class TestSkilloraServer(unittest.TestCase):
    """Tests for SkilloraServer lifecycle, concurrency, and error handling."""

    def test_server_bind_ephemeral_port_zero(self):
        """Binding to port 0 dynamically allocates an available port and starts listening."""
        server = SkilloraServer(host="127.0.0.1", port=0)
        self.assertFalse(server.is_running)

        server.start(blocking=False)
        try:
            self.assertTrue(server.is_running)
            self.assertGreater(server.port, 1024)
            self.assertEqual(server.host, "127.0.0.1")

            # Verify connection can be established
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.connect((server.host, server.port))
            req = create_request("PING", {"val": 1})
            send_packet(client_sock, req)
            res = receive_packet(client_sock)
            self.assertIsNotNone(res)
            self.assertEqual(res["status"], "SUCCESS")
            client_sock.close()
        finally:
            server.stop()
            self.assertFalse(server.is_running)

    def test_server_so_reuseaddr_immediate_restart(self):
        """Server can be stopped and immediately restarted on the same port due to SO_REUSEADDR."""
        server1 = SkilloraServer(host="127.0.0.1", port=0)
        server1.start(blocking=False)
        bound_port = server1.port
        server1.stop()
        self.assertFalse(server1.is_running)

        # Immediately restart on the exact same port
        server2 = SkilloraServer(host="127.0.0.1", port=bound_port)
        server2.start(blocking=False)
        try:
            self.assertTrue(server2.is_running)
            self.assertEqual(server2.port, bound_port)
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.connect(("127.0.0.1", bound_port))
            req = create_request("PING")
            send_packet(client_sock, req)
            res = receive_packet(client_sock)
            self.assertEqual(res["status"], "SUCCESS")
            client_sock.close()
        finally:
            server2.stop()

    def test_server_context_manager(self):
        """SkilloraServer works cleanly as a context manager with automatic shutdown."""
        with SkilloraServer(host="127.0.0.1", port=0) as server:
            self.assertTrue(server.is_running)
            allocated_port = server.port
            client_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            client_sock.connect(("127.0.0.1", allocated_port))
            send_packet(client_sock, create_request("PING"))
            res = receive_packet(client_sock)
            self.assertEqual(res["status"], "SUCCESS")
            client_sock.close()

        self.assertFalse(server.is_running)

    def test_multi_client_concurrent_requests(self):
        """Multiple concurrent client connections receive correctly correlated responses."""
        dispatcher = ActionDispatcher()

        @dispatcher.route("FACTORIAL")
        def handle_fact(payload):
            n = payload.get("n", 1)
            f = 1
            for i in range(1, n + 1):
                f *= i
            return {"fact": f}

        with SkilloraServer(host="127.0.0.1", port=0, dispatcher=dispatcher) as server:
            client_results = {}
            errors = []

            def client_worker(client_id):
                try:
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.connect((server.host, server.port))
                    for i in range(5):
                        req_id = f"c{client_id}_r{i}"
                        send_packet(s, create_request("FACTORIAL", {"n": 5 + i}, request_id=req_id))
                        res = receive_packet(s)
                        if res is None:
                            errors.append(f"Client {client_id} received None")
                            break
                        if res["request_id"] != req_id:
                            errors.append(f"Mismatched request_id: expected {req_id}, got {res['request_id']}")
                        client_results[req_id] = res["payload"]["fact"]
                    s.close()
                except Exception as ex:
                    errors.append(f"Client {client_id} exception: {ex}")

            threads = [threading.Thread(target=client_worker, args=(i,)) for i in range(8)]
            for t in threads:
                t.start()
            for t in threads:
                t.join()

            self.assertEqual(errors, [])
            self.assertEqual(len(client_results), 40)
            self.assertEqual(client_results["c0_r0"], 120)  # 5! = 120

    def test_client_abrupt_disconnect_isolation(self):
        """Abrupt disconnect of one client does not impair other active clients or crash server."""
        with SkilloraServer(host="127.0.0.1", port=0) as server:
            # Client A connects and abruptly closes without sending EOF
            sock_a = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_a.connect((server.host, server.port))
            # Force RST on close by setting SO_LINGER to 0
            sock_a.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack('ii', 1, 0))
            sock_a.close()

            # Wait briefly for server to notice disconnect
            time.sleep(0.1)

            # Client B connects and executes requests normally
            sock_b = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock_b.connect((server.host, server.port))
            send_packet(sock_b, create_request("PING", {"client": "B"}))
            res = receive_packet(sock_b)
            self.assertIsNotNone(res)
            self.assertEqual(res["status"], "SUCCESS")
            sock_b.close()

    def test_active_clients_count_tracking(self):
        """Server accurately tracks active client count on connection and disconnection."""
        with SkilloraServer(host="127.0.0.1", port=0) as server:
            self.assertEqual(server.active_clients_count, 0)

            sock1 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock1.connect((server.host, server.port))
            send_packet(sock1, create_request("PING"))
            receive_packet(sock1)

            # Give a brief moment for registration
            time.sleep(0.05)
            self.assertEqual(server.active_clients_count, 1)

            sock2 = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock2.connect((server.host, server.port))
            send_packet(sock2, create_request("PING"))
            receive_packet(sock2)

            time.sleep(0.05)
            self.assertEqual(server.active_clients_count, 2)

            sock1.close()
            time.sleep(0.1)
            self.assertEqual(server.active_clients_count, 1)

            sock2.close()
            time.sleep(0.1)
            self.assertEqual(server.active_clients_count, 0)

    def test_server_stop_terminates_all_clients_and_joins_threads(self):
        """Calling server.stop() interrupts active client sockets and terminates threads."""
        server = SkilloraServer(host="127.0.0.1", port=0)
        server.start(blocking=False)

        client_sockets = []
        for _ in range(5):
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.connect((server.host, server.port))
            send_packet(s, create_request("PING"))
            receive_packet(s)
            client_sockets.append(s)

        time.sleep(0.05)
        self.assertEqual(server.active_clients_count, 5)

        # Stop server
        start_stop = time.time()
        server.stop(timeout=2.0)
        stop_duration = time.time() - start_stop

        self.assertLess(stop_duration, 2.5)
        self.assertFalse(server.is_running)
        self.assertEqual(server.active_clients_count, 0)

        for s in client_sockets:
            try:
                s.close()
            except Exception:
                pass


if __name__ == "__main__":
    import struct
    unittest.main()
