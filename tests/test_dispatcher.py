#!/usr/bin/env python3
"""
Unit test suite for Skillora Server ActionDispatcher (server/network/dispatcher.py).
Tests route registration, route decorator, request_id correlation, exception boundaries,
built-in PING, envelope validation, and thread safety.
"""

import sys
import threading
import time
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.network.dispatcher import ActionDispatcher


class TestActionDispatcher(unittest.TestCase):
    """Tests for ActionDispatcher."""

    def setUp(self):
        self.dispatcher = ActionDispatcher()

    def test_dispatcher_ping_handler_builtin(self):
        """ActionDispatcher initializes with built-in PING handler."""
        self.assertTrue(self.dispatcher.has_action("PING"))
        req = {"action": "PING", "request_id": "req-ping-01", "payload": {"timestamp": 12345.67}}
        res = self.dispatcher.dispatch(req)
        self.assertEqual(res["action"], "PING")
        self.assertEqual(res["request_id"], "req-ping-01")
        self.assertEqual(res["status"], "SUCCESS")
        self.assertIsNone(res["error"])
        self.assertEqual(res["payload"]["echo_timestamp"], 12345.67)
        self.assertIsInstance(res["payload"]["server_time"], float)

    def test_dispatcher_registration_and_dispatch(self):
        """Registering an action and dispatching a request returns SUCCESS with payload."""
        def handle_add(payload):
            return {"sum": payload.get("a", 0) + payload.get("b", 0)}

        self.dispatcher.register("MATH_ADD", handle_add)
        self.assertTrue(self.dispatcher.has_action("MATH_ADD"))

        req = {
            "action": "MATH_ADD",
            "request_id": "req-add-99",
            "payload": {"a": 15, "b": 27},
        }
        res = self.dispatcher.dispatch(req)
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["action"], "MATH_ADD")
        self.assertEqual(res["request_id"], "req-add-99")
        self.assertEqual(res["payload"], {"sum": 42})
        self.assertIsNone(res["error"])

    def test_dispatcher_route_decorator(self):
        """Using @dispatcher.route decorator registers the action correctly."""
        @self.dispatcher.route("ECHO_ACTION")
        def handle_echo(payload):
            return {"echo": payload}

        self.assertTrue(self.dispatcher.has_action("ECHO_ACTION"))
        res = self.dispatcher.dispatch({
            "action": "ECHO_ACTION",
            "request_id": "req-echo-1",
            "payload": {"msg": "hello"},
        })
        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["payload"], {"echo": {"msg": "hello"}})

    def test_dispatcher_request_id_correlation(self):
        """Dispatcher preserves arbitrary client request_id in response."""
        for test_id in ["custom-uuid-1234", "req_abcdef0123456789", "12345"]:
            res = self.dispatcher.dispatch({
                "action": "PING",
                "request_id": test_id,
                "payload": {},
            })
            self.assertEqual(res["request_id"], test_id)

    def test_dispatcher_unregistered_action(self):
        """Dispatching an unknown action returns ERROR with descriptive error message."""
        res = self.dispatcher.dispatch({
            "action": "NON_EXISTENT_ACTION",
            "request_id": "req-unreg-01",
            "payload": {},
        })
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(res["action"], "NON_EXISTENT_ACTION")
        self.assertEqual(res["request_id"], "req-unreg-01")
        self.assertIsNone(res["payload"])
        self.assertIn("not registered", res["error"])

    def test_dispatcher_handler_exception_boundary(self):
        """Exceptions raised inside handlers are caught and returned as ERROR status."""
        def buggy_handler(payload):
            raise ZeroDivisionError("division by zero simulated")

        self.dispatcher.register("CRASH_TEST", buggy_handler)

        res = self.dispatcher.dispatch({
            "action": "CRASH_TEST",
            "request_id": "req-crash-1",
            "payload": {},
        })
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(res["action"], "CRASH_TEST")
        self.assertEqual(res["request_id"], "req-crash-1")
        self.assertIsNone(res["payload"])
        self.assertIn("division by zero", res["error"])

    def test_dispatcher_explicit_handler_error_return(self):
        """Handler returning an explicit ERROR envelope propagates error status."""
        def failing_handler(payload):
            return {"status": "ERROR", "error": "Insufficient privileges"}

        self.dispatcher.register("RESTRICTED", failing_handler)
        res = self.dispatcher.dispatch({
            "action": "RESTRICTED",
            "request_id": "req-auth-1",
            "payload": {},
        })
        self.assertEqual(res["status"], "ERROR")
        self.assertEqual(res["error"], "Insufficient privileges")

    def test_dispatcher_malformed_envelopes(self):
        """Non-dict envelopes or missing fields return clean ERROR envelopes."""
        # Non-dict inputs
        for bad_input in [None, "string", 123, [1, 2, 3]]:
            res = self.dispatcher.dispatch(bad_input)
            self.assertEqual(res["status"], "ERROR")
            self.assertIn("expected a JSON object", res["error"])

        # Missing action
        res = self.dispatcher.dispatch({"request_id": "r1", "payload": {}})
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("action", res["error"])

        # Non-dict payload
        res = self.dispatcher.dispatch({"action": "PING", "request_id": "r1", "payload": "not_a_dict"})
        self.assertEqual(res["status"], "ERROR")
        self.assertIn("dictionary", res["error"])

    def test_dispatcher_unregister_and_listing(self):
        """Unregistering removes handler; registered_actions lists registered actions."""
        self.dispatcher.register("TEMP_ACTION", lambda p: {})
        self.assertIn("TEMP_ACTION", self.dispatcher.registered_actions())
        removed = self.dispatcher.unregister("TEMP_ACTION")
        self.assertTrue(removed)
        self.assertNotIn("TEMP_ACTION", self.dispatcher.registered_actions())

    def test_dispatcher_thread_safety(self):
        """Concurrent dispatches and registrations do not raise race conditions."""
        errors = []

        def worker(thread_idx):
            for i in range(50):
                action = f"THREAD_ACT_{thread_idx}_{i}"
                self.dispatcher.register(action, lambda p: {"ok": True})
                res = self.dispatcher.dispatch({
                    "action": action,
                    "request_id": f"req-{thread_idx}-{i}",
                    "payload": {},
                })
                if res["status"] != "SUCCESS":
                    errors.append(f"Dispatch failed: {res}")

        threads = [threading.Thread(target=worker, args=(t,)) for t in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
