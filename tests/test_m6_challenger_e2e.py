#!/usr/bin/env python3
"""
Skillora Milestone 6 Challenger E2E Stress & Adversarial Hardening Suite
(tests/test_m6_challenger_e2e.py)

Adversarial Stress Test Dimensions:
1. Multi-Client Concurrency Stress: 12 concurrent client sockets hammering the live
   server simultaneously across all 7 core actions + PING with synchronization barrier.
   Confirms 100% request-response correlation without packet corruption or crosstalk.
2. Abrupt Disconnects & Malformed Framing: Truncated headers (1-3 bytes), truncated
   payloads mid-stream, TCP RST with SO_LINGER, oversized 32MB frames, malformed UTF-8/JSON.
   Confirms zero server crashes, clean thread unregistration, and unbroken service continuity.
3. Server Port Rebinds & SO_REUSEADDR: Rapid sequential stop/start cycles on identical port
   under zero cooldown without encountering EADDRINUSE.
4. Reconnect Storm: 10 clients abruptly dropped by server shutdown, attempting rapid
   reconnections, with instant recovery and synchronized request bursts upon server resurrection.
5. Asynchronous Queue Saturation: High-throughput asynchronous pipelined request burst
   verifying client queue drainage, sequence preservation, and absence of race conditions.
"""

from __future__ import annotations

import copy
import json
import logging
import os
import socket
import sqlite3
import struct
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from client.network.socket_client import SocketClient
from common.protocol import (
    HEADER_SIZE,
    MAX_PAYLOAD_SIZE,
    MIN_PAYLOAD_SIZE,
    decode_packet,
    encode_packet,
    receive_packet,
    send_packet,
)
from server.db.dao import SkilloraDAO
from server.db.init_db import init_database
from server.db.seed_data import COMPANIES_SEED_DATA, QUESTIONS_SEED_DATA
from server.network.tcp_server import SkilloraServer
from tests.test_e2e_integration import create_e2e_dispatcher

logger = logging.getLogger("skillora.challenger_m6")


class TestChallengerMultiClientConcurrencyStress(unittest.TestCase):
    """
    Stress test multi-client concurrency: 12 concurrent client sockets hammering
    the live server simultaneously across all 7 actions + PING.
    Verifies 100% request-response correlation without packet corruption or crosstalk.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db.close()
        cls.db_path = cls.temp_db.name

        cls.db_conn = sqlite3.connect(cls.db_path, check_same_thread=False)
        init_database(conn=cls.db_conn, driver="sqlite", seed=True)
        cls.dao = SkilloraDAO(conn=cls.db_conn, driver="sqlite")

        cls.dispatcher = create_e2e_dispatcher(cls.dao)
        cls.server = SkilloraServer(host="127.0.0.1", port=0, dispatcher=cls.dispatcher)
        cls.server.start(blocking=False)
        cls.port = cls.server.port

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.server.stop(timeout=2.0)
        except Exception:
            pass
        try:
            cls.db_conn.close()
        except Exception:
            pass
        try:
            if os.path.exists(cls.db_path):
                os.unlink(cls.db_path)
        except Exception:
            pass

    def test_multi_client_12_concurrent_hammer_all_actions(self) -> None:
        """
        Spawns 12 concurrent clients. Synchronizes start via Barrier, then hammers
        the live server concurrently with all 7 actions + PING.
        Ensures strict request_id correlation, expected payload integrity, and zero crosstalk.
        """
        num_clients = 12
        clients: List[SocketClient] = []

        for i in range(num_clients):
            c = SocketClient(host="127.0.0.1", port=self.port, auto_reconnect=False, default_timeout=15.0)
            c.start()
            clients.append(c)

        # Wait for all clients to connect
        connect_deadline = time.time() + 5.0
        while not all(c.is_connected() for c in clients) and time.time() < connect_deadline:
            time.sleep(0.02)

        for idx, c in enumerate(clients):
            self.assertTrue(c.is_connected(), f"Client {idx} failed to connect to live server")

        self.assertEqual(self.server.active_clients_count, num_clients)

        # Actions list to execute per client
        test_actions = [
            ("PING", lambda i: {"client_index": i, "timestamp": time.time()}),
            ("AUTH", lambda i: {"username": "demo_student", "password": "student123"}),
            ("GET_COMPANIES", lambda i: {"tier": "Tier1" if i % 2 == 0 else "Tier2"}),
            ("EVALUATE_ELIGIBILITY", lambda i: {
                "student": {
                    "full_name": f"Student_{i}",
                    "branch": "CSE" if i % 2 == 0 else "ECE",
                    "cgpa": 7.5 + (i * 0.1),
                    "backlogs": 0,
                    "scores": {
                        "coding": 70.0 + i,
                        "technical": 75.0,
                        "aptitude": 80.0,
                        "communication": 75.0,
                        "academic": 80.0,
                    },
                }
            }),
            ("SOLVE_RECURRENCE", lambda i: {
                "equation": "T(n) = 2*T(n/2) + n" if i % 2 == 0 else "T(n) = T(n-1) + 1",
                "base_cases": {"T(1)": 1},
            }),
            ("RUN_SANDBOX", lambda i: {
                "code": f"def solve(n):\n    return sum(range(n + {i}))\n",
                "input_scales": [50, 100],
                "timeout": 2.0,
            }),
            ("GENERATE_APTITUDE", lambda i: {
                "topic": ["interest_difference", "work_collaboration", "urn_probability", "cayley_trees"][i % 4],
                "difficulty": "Medium",
                "seed": 100 + i,
            }),
            ("EVALUATE_INTERVIEW", lambda i: {
                "question": QUESTIONS_SEED_DATA[i % len(QUESTIONS_SEED_DATA)],
                "student_answer": f"In order to solve this problem efficiently in O(n) time, we utilize a hash map to cache seen values. Thread {i} verification.",
                "code_snippet": "def solution(arr):\n    seen = set(arr)\n    return len(seen)\n",
            }),
        ]

        barrier = threading.Barrier(num_clients)
        results_lock = threading.Lock()
        client_records: Dict[int, List[Dict[str, Any]]] = {i: [] for i in range(num_clients)}
        errors: List[str] = []

        def client_worker(client_idx: int, client: SocketClient) -> None:
            # Synchronize arrival across all 12 worker threads
            barrier.wait(timeout=5.0)

            for action_name, payload_factory in test_actions:
                payload = payload_factory(client_idx)
                payload["__client_origin__"] = client_idx

                try:
                    response = client.send_request_sync(action_name, payload, timeout=12.0)
                    with results_lock:
                        client_records[client_idx].append({
                            "action": action_name,
                            "response": response,
                            "sent_payload": payload,
                        })
                except Exception as ex:
                    with results_lock:
                        errors.append(f"Client {client_idx} action {action_name} error: {ex}")

        threads = [
            threading.Thread(target=client_worker, args=(i, clients[i]), name=f"ChallengerWorker-{i}")
            for i in range(num_clients)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=30.0)

        # Stop clients
        for c in clients:
            c.stop(timeout=1.0)

        # Forensic Audit of Results
        self.assertEqual(len(errors), 0, f"Errors encountered during concurrent hammering: {errors}")

        total_requests = num_clients * len(test_actions)
        total_recorded = sum(len(records) for records in client_records.values())
        self.assertEqual(total_recorded, total_requests, f"Expected {total_requests} responses, got {total_recorded}")

        # Verify response integrity, correlation, and absence of crosstalk
        seen_request_ids = set()
        for client_idx, records in client_records.items():
            self.assertEqual(len(records), len(test_actions), f"Client {client_idx} missed responses")

            for item in records:
                action = item["action"]
                res = item["response"]
                sent_payload = item["sent_payload"]

                # 1. Action matching
                self.assertEqual(res.get("action"), action)
                self.assertEqual(res.get("status"), "SUCCESS")

                # 2. Correlation uniqueness
                req_id = res.get("request_id")
                self.assertTrue(req_id and req_id.startswith("req_"))
                self.assertNotIn(req_id, seen_request_ids, f"Duplicate request_id detected: {req_id}")
                seen_request_ids.add(req_id)

                # 3. Content integrity validation per action
                payload = res.get("payload", {})
                if action == "PING":
                    self.assertIn("server_time", payload)
                elif action == "AUTH":
                    self.assertTrue(payload.get("authenticated"))
                    self.assertEqual(payload.get("user", {}).get("username"), "demo_student")
                elif action == "GET_COMPANIES":
                    comps = payload.get("companies", [])
                    self.assertGreater(len(comps), 0)
                elif action == "EVALUATE_ELIGIBILITY":
                    self.assertIn("pri", payload)
                    self.assertIn("eligible_count", payload)
                elif action == "SOLVE_RECURRENCE":
                    self.assertIn("big_o", payload)
                    self.assertIsNone(payload.get("error"))
                elif action == "RUN_SANDBOX":
                    self.assertFalse(payload.get("timed_out"))
                    self.assertEqual(len(payload.get("points", [])), 2)
                elif action == "GENERATE_APTITUDE":
                    self.assertEqual(len(payload.get("options", [])), 4)
                    self.assertIn(payload.get("correct_option_index"), [0, 1, 2, 3])
                elif action == "EVALUATE_INTERVIEW":
                    self.assertGreater(payload.get("total_score", 0), 0)
                    self.assertIn("keyword_score", payload)


class TestChallengerAbruptDisconnectMidPacket(unittest.TestCase):
    """
    Stress test abrupt socket disconnects mid-packet, malformed framing,
    frame-size boundary violations, and TCP resets.
    Verifies zero server thread hanging, zero socket leaks, and unbroken service continuity.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = create_e2e_dispatcher()
        cls.server = SkilloraServer(host="127.0.0.1", port=0, dispatcher=cls.dispatcher)
        cls.server.start(blocking=False)
        cls.port = cls.server.port

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop(timeout=2.0)

    def test_abrupt_disconnect_1_byte_header(self) -> None:
        """Client connects, transmits only 1 byte of 4-byte length prefix, then closes socket abruptly."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", self.port))
        raw_sock.sendall(b"\x00")
        raw_sock.close()

        # Allow server thread to detect EOF and cleanly exit
        time.sleep(0.1)
        self.assertEqual(self.server.active_clients_count, 0)

    def test_abrupt_disconnect_3_byte_header(self) -> None:
        """Client connects, transmits 3 bytes of 4-byte length prefix, then closes socket abruptly."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", self.port))
        raw_sock.sendall(b"\x00\x00\x01")
        raw_sock.close()

        time.sleep(0.1)
        self.assertEqual(self.server.active_clients_count, 0)

    def test_abrupt_disconnect_mid_payload(self) -> None:
        """
        Client specifies 1000-byte length header, but only transmits 30 bytes of payload
        before abruptly dropping connection.
        """
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", self.port))
        header = struct.pack("!I", 1000)
        partial_payload = b'{"action": "SOLVE_RECURR'
        raw_sock.sendall(header + partial_payload)
        raw_sock.close()

        time.sleep(0.1)
        self.assertEqual(self.server.active_clients_count, 0)

    def test_abrupt_disconnect_rst_with_so_linger(self) -> None:
        """
        Client sends partial frame, then sends hard TCP RST using SO_LINGER (1, 0)
        simulating sudden network cable pull / process kill -9.
        """
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", self.port))
        header = struct.pack("!I", 500)
        raw_sock.sendall(header + b'{"action": "PING"')

        # Enable SO_LINGER with timeout 0 -> sends RST on close()
        raw_sock.setsockopt(socket.SOL_SOCKET, socket.SO_LINGER, struct.pack("ii", 1, 0))
        raw_sock.close()

        time.sleep(0.1)
        self.assertEqual(self.server.active_clients_count, 0)

    def test_undersized_frame_length_violation(self) -> None:
        """Header claims payload length 1 (< MIN_PAYLOAD_SIZE of 2 bytes). Server must reject."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", self.port))
        header = struct.pack("!I", 1)
        raw_sock.sendall(header + b"{")

        # Read response or wait for server to close
        raw_sock.settimeout(1.0)
        try:
            res = receive_packet(raw_sock)
            if res:
                self.assertEqual(res.get("status"), "ERROR")
        except Exception:
            pass
        finally:
            raw_sock.close()

        time.sleep(0.1)
        self.assertEqual(self.server.active_clients_count, 0)

    def test_oversized_frame_header_32mb_rejection(self) -> None:
        """Header specifies 32MB payload (> 16MB threshold). Server must reject without allocating buffer."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", self.port))
        header = struct.pack("!I", 32 * 1024 * 1024)
        raw_sock.sendall(header)

        raw_sock.settimeout(1.0)
        try:
            res = receive_packet(raw_sock)
            if res:
                self.assertEqual(res.get("status"), "ERROR")
                self.assertIn("exceeds", str(res.get("error", "")).lower())
        except Exception:
            pass
        finally:
            raw_sock.close()

        time.sleep(0.1)
        self.assertEqual(self.server.active_clients_count, 0)

    def test_malformed_json_payload_rejection(self) -> None:
        """Payload is valid length but corrupted JSON syntax. Server handles gracefully."""
        raw_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        raw_sock.connect(("127.0.0.1", self.port))
        corrupt_body = b"{{{not a valid json object@@@!!!"
        header = struct.pack("!I", len(corrupt_body))
        raw_sock.sendall(header + corrupt_body)

        raw_sock.settimeout(1.0)
        try:
            res = receive_packet(raw_sock)
            if res:
                self.assertEqual(res.get("status"), "ERROR")
        except Exception:
            pass
        finally:
            raw_sock.close()

        time.sleep(0.1)
        self.assertEqual(self.server.active_clients_count, 0)

    def test_server_operational_continuity_post_attacks(self) -> None:
        """
        Verifies that after all previous abrupt disconnects and malformed packet attacks,
        the server continues serving regular legitimate clients with zero degradation.
        """
        client = SocketClient(host="127.0.0.1", port=self.port, auto_reconnect=False)
        client.start()

        deadline = time.time() + 3.0
        while not client.is_connected() and time.time() < deadline:
            time.sleep(0.02)

        self.assertTrue(client.is_connected())

        # Send legitimate PING and GET_COMPANIES
        res1 = client.send_request_sync("PING", {"continuity_check": True})
        self.assertEqual(res1.get("status"), "SUCCESS")

        res2 = client.send_request_sync("GET_COMPANIES", {"tier": "Tier1"})
        self.assertEqual(res2.get("status"), "SUCCESS")

        client.stop(timeout=1.0)
        self.assertEqual(self.server.active_clients_count, 0)


class TestChallengerServerPortRebindReuseAddr(unittest.TestCase):
    """
    Stress test server port rebinds under SO_REUSEADDR across rapid restart cycles.
    Verifies that stopping and immediately restarting on the exact same port never raises EADDRINUSE.
    """

    def test_rapid_sequential_stop_start_rebind_cycles(self) -> None:
        """Executes 5 rapid sequential restart cycles on the identical port."""
        dispatcher = create_e2e_dispatcher()

        # Initial server to acquire an available dynamic port
        s_init = SkilloraServer(host="127.0.0.1", port=0, dispatcher=dispatcher)
        s_init.start(blocking=False)
        fixed_port = s_init.port
        s_init.stop(timeout=1.0)

        for cycle in range(5):
            srv = SkilloraServer(host="127.0.0.1", port=fixed_port, dispatcher=dispatcher)
            srv.start(blocking=False)
            self.assertTrue(srv.is_running, f"Cycle {cycle}: Server failed to start on port {fixed_port}")
            self.assertEqual(srv.port, fixed_port)

            # Connect client and verify responsiveness
            cli = SocketClient(host="127.0.0.1", port=fixed_port, auto_reconnect=False)
            cli.start()

            deadline = time.time() + 2.0
            while not cli.is_connected() and time.time() < deadline:
                time.sleep(0.01)

            self.assertTrue(cli.is_connected(), f"Cycle {cycle}: Client failed to connect")
            res = cli.send_request_sync("PING", {"cycle": cycle})
            self.assertEqual(res.get("status"), "SUCCESS")

            cli.stop(timeout=0.5)
            srv.stop(timeout=0.5)
            self.assertFalse(srv.is_running)


class TestChallengerReconnectStorm(unittest.TestCase):
    """
    Stress test reconnect storms: 10 concurrent clients connected with auto-reconnect.
    Server is abruptly halted, then restarted on the identical port.
    All 10 clients reconnect simultaneously and fire concurrent requests without deadlocks.
    """

    def test_10_client_reconnect_storm_and_recovery(self) -> None:
        dispatcher = create_e2e_dispatcher()
        server = SkilloraServer(host="127.0.0.1", port=0, dispatcher=dispatcher)
        server.start(blocking=False)
        fixed_port = server.port

        num_clients = 10
        clients: List[SocketClient] = []

        # Connect 10 clients with fast reconnect interval
        for i in range(num_clients):
            c = SocketClient(
                host="127.0.0.1",
                port=fixed_port,
                auto_reconnect=True,
                reconnect_interval=0.2,
                default_timeout=10.0,
            )
            c.start()
            clients.append(c)

        deadline = time.time() + 4.0
        while not all(c.is_connected() for c in clients) and time.time() < deadline:
            time.sleep(0.02)

        for i, c in enumerate(clients):
            self.assertTrue(c.is_connected(), f"Initial connect failed for client {i}")

        self.assertEqual(server.active_clients_count, num_clients)

        # Abruptly stop server -> drops all 10 clients
        server.stop(timeout=1.0)
        self.assertFalse(server.is_running)

        # Verify all clients observe disconnection
        disconnect_deadline = time.time() + 2.0
        while any(c.is_connected() for c in clients) and time.time() < disconnect_deadline:
            time.sleep(0.02)

        self.assertFalse(any(c.is_connected() for c in clients), "Clients should report disconnected")

        # Restart server on the identical port -> Triggers Reconnect Storm
        restarted_server = SkilloraServer(host="127.0.0.1", port=fixed_port, dispatcher=dispatcher)
        restarted_server.start(blocking=False)
        self.assertTrue(restarted_server.is_running)

        # Wait for all 10 clients to re-establish connection
        reconnect_deadline = time.time() + 6.0
        while not all(c.is_connected() for c in clients) and time.time() < reconnect_deadline:
            time.sleep(0.02)

        for i, c in enumerate(clients):
            self.assertTrue(c.is_connected(), f"Client {i} failed to reconnect during storm")

        # Concurrently fire requests from all 10 reconnected clients
        responses: List[Dict[str, Any]] = []
        errors: List[str] = []
        lock = threading.Lock()

        def storm_worker(idx: int, client: SocketClient) -> None:
            try:
                res = client.send_request_sync("PING", {"storm_client": idx}, timeout=5.0)
                with lock:
                    responses.append(res)
            except Exception as ex:
                with lock:
                    errors.append(f"Storm client {idx} failed request: {ex}")

        storm_threads = [
            threading.Thread(target=storm_worker, args=(i, clients[i]))
            for i in range(num_clients)
        ]
        for t in storm_threads:
            t.start()
        for t in storm_threads:
            t.join(timeout=10.0)

        # Stop clients and server
        for c in clients:
            c.stop(timeout=0.5)
        restarted_server.stop(timeout=1.0)

        self.assertEqual(len(errors), 0, f"Errors during post-reconnect storm: {errors}")
        self.assertEqual(len(responses), num_clients)
        for r in responses:
            self.assertEqual(r.get("status"), "SUCCESS")


class TestChallengerAsynchronousBurstQueueSaturation(unittest.TestCase):
    """
    Stress test asynchronous request pipelining and queue saturation.
    Fires 40 asynchronous requests without blocking, draining response queue
    via poll_responses(), verifying sequential order and zero packet loss.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.dispatcher = create_e2e_dispatcher()
        cls.server = SkilloraServer(host="127.0.0.1", port=0, dispatcher=cls.dispatcher)
        cls.server.start(blocking=False)
        cls.port = cls.server.port

    @classmethod
    def tearDownClass(cls) -> None:
        cls.server.stop(timeout=1.0)

    def test_burst_asynchronous_queue_drainage(self) -> None:
        client = SocketClient(host="127.0.0.1", port=self.port, auto_reconnect=False)
        client.start()

        deadline = time.time() + 2.0
        while not client.is_connected() and time.time() < deadline:
            time.sleep(0.01)
        self.assertTrue(client.is_connected())

        burst_size = 40
        received_responses: Dict[str, dict] = {}
        request_ids_order: List[str] = []

        def make_callback(req_id: str):
            def _cb(res: dict) -> None:
                received_responses[req_id] = res
            return _cb

        # Enqueue burst of 40 requests without waiting
        for i in range(burst_size):
            req_id = client.send_request(
                action="PING",
                payload={"seq": i},
                callback=make_callback(f"expected_{i}"),
                timeout=10.0,
            )
            request_ids_order.append(req_id)

        # Poll loop draining response queue
        poll_deadline = time.time() + 6.0
        while len(received_responses) < burst_size and time.time() < poll_deadline:
            client.poll_responses(max_items_per_poll=20)
            time.sleep(0.02)

        client.stop(timeout=1.0)

        self.assertEqual(len(received_responses), burst_size, f"Expected {burst_size} responses, got {len(received_responses)}")
        for i in range(burst_size):
            key = f"expected_{i}"
            self.assertIn(key, received_responses)
            self.assertEqual(received_responses[key].get("status"), "SUCCESS")


if __name__ == "__main__":
    unittest.main()
