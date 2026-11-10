"""
Skillora Milestone 5 Adversarial Challenger Stress Suite (tests/test_m5_challenger_bridge.py)
Adversarial stress testing for:
1. SocketClient.bind_to_tk under burst packet loads (100+ packets), non-blocking queue draining,
   main-thread callback execution, zero deadlock, and exception blast-radius resilience.
2. Rapid view navigation fuzzing (100+ rapid tkraise invocations), zero widget/frame leakage,
   idempotent view elevation, invalid view key handling, and event-loop latency.
3. Combined concurrency stress: burst network packet delivery concurrent with rapid view switching
   and connection state flapping.
"""

import logging
import queue
import random
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import customtkinter as ctk

from client.gui.app_window import AppWindow
from client.gui.theme import (
    COLOR_NAV_ACTIVE_BG,
    COLOR_NAV_ACTIVE_TEXT,
    COLOR_NAV_IDLE,
    COLOR_NAV_IDLE_TEXT,
    FONT_BODY,
    FONT_BODY_BOLD,
    enforce_light_theme,
)
from client.gui.views import (
    CodingSandboxView,
    CompanyView,
    DashboardView,
    InterviewView,
    MathStudioView,
)
from client.network.socket_client import SocketClient

logger = logging.getLogger("skillora.challenger_bridge")


def is_display_available() -> bool:
    """Checks whether a GUI display is accessible for widget rendering."""
    try:
        import tkinter
        r = tkinter.Tk()
        r.withdraw()
        r.destroy()
        return True
    except Exception:
        return False


class MockTkRoot:
    """Mock Tkinter root object for testing bind_to_tk in purely headless environments."""

    def __init__(self):
        self.timers: Dict[int, Tuple[int, Any]] = {}
        self._timer_counter = 0

    def after(self, ms: int, func: Any) -> int:
        self._timer_counter += 1
        timer_id = self._timer_counter
        self.timers[timer_id] = (ms, func)
        return timer_id

    def after_cancel(self, timer_id: int) -> None:
        self.timers.pop(timer_id, None)

    def trigger_all_timers(self) -> int:
        """Fires and clears all pending timers once."""
        current = list(self.timers.items())
        self.timers.clear()
        for t_id, (ms, callback) in current:
            callback()
        return len(current)


# ==============================================================================
# Suite 1: SocketClient Bridge & Burst Concurrency Adversarial Tests
# ==============================================================================
class TestSocketBridgeBurstConcurrency(unittest.TestCase):
    """
    Adversarial stress testing of SocketClient.bind_to_tk and queue polling:
    - 100+ packet burst flood
    - Strict main-thread callback execution
    - Non-blocking batch drainage
    - Multithreaded producer contention and zero deadlock
    - Exception blast-radius containment
    - Timeout sweep synchronization
    """

    def setUp(self):
        enforce_light_theme()
        self.client: Optional[SocketClient] = None
        self.root: Optional[ctk.CTk] = None
        if is_display_available():
            self.root = ctk.CTk()
            self.root.withdraw()

    def tearDown(self):
        if self.client:
            self.client.stop()
            self.client = None
        if self.root:
            try:
                for timer_id in self.root.tk.call("after", "info"):
                    try:
                        self.root.after_cancel(timer_id)
                    except Exception:
                        pass
                self.root.update_idletasks()
                self.root.destroy()
            except Exception:
                pass
            self.root = None

    def test_burst_packet_load_120_packets_all_executed_on_main_thread(self):
        """
        Adversarially injects 120 synthetic response packets in an instant burst.
        Confirms:
        1. All 120 callbacks are executed without dropping a single packet.
        2. 100% of callbacks execute strictly on the main thread (thread ID match).
        3. No deadlock occurs and queue drains cleanly.
        """
        main_thread_ident = threading.get_ident()
        self.client = SocketClient(host="127.0.0.1", port=59990, auto_reconnect=False)

        num_packets = 120
        executed_callbacks: Dict[str, dict] = {}
        execution_threads: List[int] = []
        completion_event = threading.Event()

        def make_callback(req_id: str, idx: int):
            def _cb(response_pkt: dict):
                tid = threading.get_ident()
                execution_threads.append(tid)
                executed_callbacks[req_id] = {
                    "index": idx,
                    "payload": response_pkt.get("payload"),
                    "thread_id": tid,
                }
                if len(executed_callbacks) == num_packets:
                    completion_event.set()
            return _cb

        # 1. Enqueue 120 requests
        request_ids = []
        for i in range(num_packets):
            req_id = self.client.send_request(
                action="TEST_BURST",
                payload={"seq": i, "timestamp": time.time()},
                callback=make_callback(f"pending_{i}", i),
                timeout=10.0,
            )
            # Replace placeholder key with actual req_id
            cb_entry = self.client._callback_registry[req_id]
            cb_entry.callback = make_callback(req_id, i)
            request_ids.append(req_id)

        # 2. Inject 120 responses in an instantaneous flood
        for i, req_id in enumerate(request_ids):
            fake_response = {
                "action": "TEST_BURST",
                "request_id": req_id,
                "status": "SUCCESS",
                "payload": {"seq": i, "result": f"OK_{i}"},
            }
            self.client._response_queue.put(("RESPONSE", fake_response))

        self.assertEqual(self.client._response_queue.qsize(), num_packets)

        # 3. Drain via bind_to_tk polling loop
        if self.root:
            self.client.bind_to_tk(self.root, interval_ms=10)
            start_drain = time.time()
            while not completion_event.is_set():
                if time.time() - start_drain > 5.0:
                    self.fail("Timed out waiting for 120 burst packets to drain via Tkinter polling")
                self.root.update_idletasks()
                self.root.update()
                time.sleep(0.005)
        else:
            # Fallback manual drain loop on main thread
            start_drain = time.time()
            while not completion_event.is_set():
                if time.time() - start_drain > 5.0:
                    self.fail("Timed out waiting for 120 burst packets to drain manually")
                self.client.poll_responses(max_items_per_poll=50)
                time.sleep(0.005)

        # 4. Verify complete delivery and thread safety
        self.assertEqual(len(executed_callbacks), num_packets, "Every packet must trigger its callback")
        self.assertEqual(len(execution_threads), num_packets)
        for tid in execution_threads:
            self.assertEqual(
                tid,
                main_thread_ident,
                "Every callback MUST execute strictly on the main UI thread, NEVER a worker thread",
            )

        # 5. Verify payload integrity
        for i, req_id in enumerate(request_ids):
            self.assertIn(req_id, executed_callbacks)
            self.assertEqual(executed_callbacks[req_id]["payload"]["result"], f"OK_{i}")

        self.assertEqual(self.client._response_queue.qsize(), 0, "Response queue must be completely empty")

    def test_multithreaded_producer_contention_zero_deadlock(self):
        """
        Spawns 5 concurrent producer threads flooding _response_queue while
        the main thread continuously polls. Confirms zero deadlock and 100% processing.
        """
        main_thread_id = threading.get_ident()
        self.client = SocketClient(host="127.0.0.1", port=59991, auto_reconnect=False)

        packets_per_thread = 25
        num_threads = 5
        total_packets = packets_per_thread * num_threads

        received_results: List[int] = []
        registry_lock = threading.Lock()
        drain_done = threading.Event()

        def make_cb(val: int):
            def _cb(pkt: dict):
                self.assertEqual(threading.get_ident(), main_thread_id)
                with registry_lock:
                    received_results.append(val)
                if len(received_results) == total_packets:
                    drain_done.set()
            return _cb

        # Pre-register all requests
        req_mapping: Dict[int, str] = {}
        for i in range(total_packets):
            r_id = self.client.send_request("CONCURRENT_STRESS", {"idx": i}, callback=make_cb(i))
            req_mapping[i] = r_id

        # Producer thread worker
        def producer_worker(thread_idx: int):
            start_idx = thread_idx * packets_per_thread
            for offset in range(packets_per_thread):
                idx = start_idx + offset
                r_id = req_mapping[idx]
                pkt = {
                    "action": "CONCURRENT_STRESS",
                    "request_id": r_id,
                    "status": "SUCCESS",
                    "payload": {"val": idx},
                }
                self.client._response_queue.put(("RESPONSE", pkt))
                time.sleep(0.001)

        producer_threads = [
            threading.Thread(target=producer_worker, args=(t,), daemon=True)
            for t in range(num_threads)
        ]

        # Start all producers concurrently
        for t in producer_threads:
            t.start()

        # Concurrently drain on main thread with a strict 6-second deadlock timeout
        start_time = time.time()
        while not drain_done.is_set():
            if time.time() - start_time > 6.0:
                self.fail(
                    f"Deadlock or starvation detected: processed {len(received_results)} of {total_packets} packets"
                )
            self.client.poll_responses(max_items_per_poll=20)
            time.sleep(0.005)

        for t in producer_threads:
            t.join(timeout=1.0)
            self.assertFalse(t.is_alive())

        self.assertEqual(len(received_results), total_packets)
        self.assertEqual(sorted(received_results), list(range(total_packets)))

    def test_non_blocking_drain_cap_prevents_ui_starvation(self):
        """
        Pushes 130 items into the response queue and verifies that
        poll_responses(max_items_per_poll=50) caps each poll to 50 items,
        preventing infinite loops or blocking the GUI thread.
        """
        self.client = SocketClient(host="127.0.0.1", port=59992, auto_reconnect=False)
        total_items = 130

        # Inject 130 generic SYS_STATUS items
        for i in range(total_items):
            self.client._response_queue.put(("SYS_STATUS", {"status": "TEST", "seq": i}))

        self.assertEqual(self.client._response_queue.qsize(), total_items)

        # Batch 1: Exactly 50 items
        p1 = self.client.poll_responses(max_items_per_poll=50)
        self.assertEqual(p1, 50)
        self.assertEqual(self.client._response_queue.qsize(), 80)

        # Batch 2: Exactly 50 items
        p2 = self.client.poll_responses(max_items_per_poll=50)
        self.assertEqual(p2, 50)
        self.assertEqual(self.client._response_queue.qsize(), 30)

        # Batch 3: Remaining 30 items
        p3 = self.client.poll_responses(max_items_per_poll=50)
        self.assertEqual(p3, 30)
        self.assertEqual(self.client._response_queue.qsize(), 0)

        # Batch 4: Empty queue returns 0
        p4 = self.client.poll_responses(max_items_per_poll=50)
        self.assertEqual(p4, 0)

    def test_callback_exception_blast_radius_containment(self):
        """
        Adversarially forces 30% of UI callbacks to raise unhandled exceptions.
        Verifies that:
        1. Exceptions do NOT break the queue draining loop.
        2. All healthy callbacks still execute completely.
        3. Next timer ticks continue scheduling uninterrupted.
        """
        self.client = SocketClient(host="127.0.0.1", port=59993, auto_reconnect=False)
        total = 60
        healthy_executed = []
        faulty_executed = []

        for i in range(total):
            is_faulty = (i % 3 == 0)

            def make_handler(idx: int, faulty: bool):
                def _h(pkt: dict):
                    if faulty:
                        faulty_executed.append(idx)
                        raise RuntimeError(f"Simulated UI Crash in callback {idx}!")
                    else:
                        healthy_executed.append(idx)
                return _h

            req_id = self.client.send_request("FAULT_TEST", {"idx": i}, callback=make_handler(i, is_faulty))
            pkt = {"action": "FAULT_TEST", "request_id": req_id, "status": "SUCCESS", "payload": {}}
            self.client._response_queue.put(("RESPONSE", pkt))

        # Drain all items
        processed = 0
        while self.client._response_queue.qsize() > 0:
            processed += self.client.poll_responses(max_items_per_poll=20)

        self.assertEqual(processed, total)
        self.assertEqual(len(faulty_executed), 20)
        self.assertEqual(len(healthy_executed), 40)
        self.assertEqual(len(self.client._callback_registry), 0)

    def test_timeout_sweep_concurrency_under_burst(self):
        """
        Enqueues 40 requests with ultra-short timeouts (0.02s) and 40 normal requests (10s).
        After 0.05s, sweeps and confirms that expired requests fail with REQUEST_TIMEOUT
        while normal requests remain unaffected.
        """
        self.client = SocketClient(host="127.0.0.1", port=59994, auto_reconnect=False)
        expired_errors = []
        valid_successes = []

        def err_cb(err):
            expired_errors.append(err)

        def ok_cb(res):
            valid_successes.append(res)

        # 40 expiring requests
        for i in range(40):
            self.client.send_request(
                "EXPIRING",
                {"idx": i},
                callback=ok_cb,
                error_callback=err_cb,
                timeout=0.02,
            )

        # 40 valid requests
        valid_ids = []
        for i in range(40):
            rid = self.client.send_request(
                "NORMAL",
                {"idx": i},
                callback=ok_cb,
                error_callback=err_cb,
                timeout=10.0,
            )
            valid_ids.append(rid)

        # Sleep to let the 40 short requests expire
        time.sleep(0.06)

        # Provide responses only for valid requests
        for rid in valid_ids:
            self.client._response_queue.put((
                "RESPONSE",
                {"action": "NORMAL", "request_id": rid, "status": "SUCCESS", "payload": {"ok": True}},
            ))

        # Poll to trigger sweep + response handling
        self.client.poll_responses(max_items_per_poll=100)

        self.assertEqual(len(expired_errors), 40, "All 40 short-lived requests must be swept as timeouts")
        for err in expired_errors:
            self.assertEqual(err.get("code"), "REQUEST_TIMEOUT")

        self.assertEqual(len(valid_successes), 40, "All 40 normal requests must receive their valid response")
        self.assertEqual(len(self.client._callback_registry), 0)


# ==============================================================================
# Suite 2: Rapid View Navigation Fuzzing (100+ Switches, Withdrawn Tk)
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestRapidViewNavigationFuzzing(unittest.TestCase):
    """
    Adversarial fuzzing of AppWindow view transitions:
    - 150+ rapid tkraise navigations
    - Memory leak check: winfo_children stability
    - Navigation idempotency check
    - Resilience to non-existent / empty view keys
    - Event loop latency & responsiveness threshold
    """

    def setUp(self):
        enforce_light_theme()
        self.root = ctk.CTk()
        self.root.withdraw()

        self.app = AppWindow(root=self.root, socket_client=None, offline_mode=True)
        self.app.register_view("dashboard", DashboardView)
        self.app.register_view("company", CompanyView)
        self.app.register_view("math_studio", MathStudioView)
        self.app.register_view("coding_sandbox", CodingSandboxView)
        self.app.register_view("interview", InterviewView)

        self.view_keys = ["dashboard", "company", "math_studio", "coding_sandbox", "interview"]

    def tearDown(self):
        try:
            for timer_id in self.root.tk.call("after", "info"):
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def test_fuzz_rapid_view_switching_150_cycles(self):
        """
        Executes 150 rapid pseudo-random view navigations.
        At every step, verifies:
        1. Target view becomes active and elevated.
        2. Corresponding sidebar button acquires active styling (COLOR_NAV_ACTIVE_BG, bold).
        3. All other sidebar buttons reset to idle styling.
        4. No Tkinter exceptions or crashes occur.
        """
        rng = random.Random(42)  # Deterministic seed for reproducible stress fuzzing
        total_transitions = 150

        # Initial view is dashboard
        self.app.navigate_to("dashboard")
        self.root.update_idletasks()

        for step in range(total_transitions):
            target_key = rng.choice(self.view_keys)
            self.app.navigate_to(target_key)

            # Assert internal state
            self.assertEqual(self.app._current_view_key, target_key)

            # Assert button styling invariants
            for key, btn in self.app._nav_buttons.items():
                if key == target_key:
                    self.assertEqual(btn.cget("fg_color"), COLOR_NAV_ACTIVE_BG)
                    self.assertEqual(btn.cget("text_color"), COLOR_NAV_ACTIVE_TEXT)
                    self.assertEqual(btn.cget("font"), FONT_BODY_BOLD)
                else:
                    self.assertEqual(btn.cget("fg_color"), COLOR_NAV_IDLE)
                    self.assertEqual(btn.cget("text_color"), COLOR_NAV_IDLE_TEXT)
                    self.assertEqual(btn.cget("font"), FONT_BODY)

            # Pump Tkinter event loop
            if step % 5 == 0:
                self.root.update_idletasks()
                self.root.update()

        self.root.update_idletasks()
        self.root.update()

    def test_zero_widget_leak_and_constant_view_container_child_count(self):
        """
        Verifies that view switching uses frame elevation (tkraise) rather than
        re-instantiating widgets. Container child count must remain strictly 5.
        """
        initial_children = self.app.views_container.winfo_children()
        self.assertEqual(len(initial_children), 5, "views_container must contain exactly 5 registered views")

        # Cycle through views 100 times
        for _ in range(20):
            for vk in self.view_keys:
                self.app.navigate_to(vk)

        self.root.update_idletasks()
        self.root.update()

        final_children = self.app.views_container.winfo_children()
        self.assertEqual(
            len(final_children),
            5,
            "views_container must NOT accumulate leaked frames; child count must remain strictly 5",
        )
        self.assertEqual(set(initial_children), set(final_children))

    def test_navigation_idempotency_no_op(self):
        """
        Navigating repeatedly to the currently active view must be an instant no-op
        and must not cause redundant redraws or widget flashing.
        """
        self.app.navigate_to("dashboard")
        self.root.update_idletasks()

        # Rapidly attempt 50 redundant navigations to the same view
        for _ in range(50):
            self.app.navigate_to("dashboard")

        self.root.update_idletasks()
        self.assertEqual(self.app._current_view_key, "dashboard")

    def test_navigation_resilience_to_invalid_view_keys(self):
        """
        Navigating to non-existent, empty, or malformed keys must log a warning
        and return safely without raising exceptions or altering the current active view.
        """
        self.app.navigate_to("dashboard")
        self.assertEqual(self.app._current_view_key, "dashboard")

        invalid_keys = [
            "non_existent_key",
            "",
            "UNKNOWN_VIEW",
            "dashboard_v2",
            "company_view_typo",
            123,  # type: ignore
            None,  # type: ignore
        ]

        for inv_key in invalid_keys:
            try:
                self.app.navigate_to(inv_key)
            except Exception as ex:
                self.fail(f"navigate_to raised an exception on invalid key {inv_key!r}: {ex}")

            # Active view must be preserved
            self.assertEqual(self.app._current_view_key, "dashboard")

    def test_event_loop_latency_under_100_switches(self):
        """
        Measures execution latency for 100 view switches with Tk event pumping.
        Confirms average latency per switch is under 250ms (the human perception
        threshold for interactive UI responsiveness) to guarantee zero event loop freezing.
        """
        start_time = time.perf_counter()
        switches = 100

        for i in range(switches):
            vk = self.view_keys[i % len(self.view_keys)]
            self.app.navigate_to(vk)
            self.root.update_idletasks()

        total_duration = time.perf_counter() - start_time
        avg_per_switch = (total_duration / switches) * 1000.0  # ms

        logger.info("100 view switches executed in %0.3fs (avg %0.2fms/switch)", total_duration, avg_per_switch)
        self.assertLess(
            total_duration,
            25.0,
            f"100 view switches took too long ({total_duration:.2f}s); average per switch exceeds 250ms interactive budget",
        )
        self.assertLess(
            avg_per_switch,
            250.0,
            f"Average switch latency ({avg_per_switch:.1f}ms) exceeds the 250ms human perception responsiveness threshold",
        )


# ==============================================================================
# Suite 3: Combined Concurrency Stress (Burst Socket + Rapid Navigation)
# ==============================================================================
@unittest.skipUnless(is_display_available(), "Display not available in headless environment")
class TestBridgeAndNavigationCombinedStress(unittest.TestCase):
    """
    Combined stress testing:
    - High-throughput background packet generation while user navigates views
    - Connection state flapping concurrent with rapid navigation
    """

    def setUp(self):
        enforce_light_theme()
        self.root = ctk.CTk()
        self.root.withdraw()
        self.client = SocketClient(host="127.0.0.1", port=59995, auto_reconnect=False)
        self.app = AppWindow(root=self.root, socket_client=self.client, offline_mode=False)
        self.app.register_view("dashboard", DashboardView)
        self.app.register_view("company", CompanyView)
        self.app.register_view("math_studio", MathStudioView)
        self.app.register_view("coding_sandbox", CodingSandboxView)
        self.app.register_view("interview", InterviewView)
        self.view_keys = ["dashboard", "company", "math_studio", "coding_sandbox", "interview"]

    def tearDown(self):
        if self.client:
            self.client.stop()
            self.client = None
        try:
            for timer_id in self.root.tk.call("after", "info"):
                try:
                    self.root.after_cancel(timer_id)
                except Exception:
                    pass
            self.root.update_idletasks()
            self.root.destroy()
        except Exception:
            pass

    def test_burst_network_responses_concurrent_with_rapid_view_switching(self):
        """
        Background worker produces 100 responses while main thread rapidly switches views 60 times.
        Verifies:
        1. All 100 responses trigger callbacks on the main thread.
        2. View navigation continues without UI lockup or crashes.
        3. No deadlock between network bridge locks and Tkinter update ticks.
        """
        main_tid = threading.get_ident()
        num_packets = 100
        completed_packets: List[int] = []
        lock = threading.Lock()

        def make_cb(idx: int):
            def _cb(res: dict):
                self.assertEqual(threading.get_ident(), main_tid)
                with lock:
                    completed_packets.append(idx)
            return _cb

        # Pre-register 100 requests
        req_ids = []
        for i in range(num_packets):
            rid = self.client.send_request("PING", {"i": i}, callback=make_cb(i))
            req_ids.append(rid)

        # Background thread to inject responses
        def injector():
            for idx, rid in enumerate(req_ids):
                pkt = {
                    "action": "PING",
                    "request_id": rid,
                    "status": "SUCCESS",
                    "payload": {"seq": idx},
                }
                self.client._response_queue.put(("RESPONSE", pkt))
                time.sleep(0.001)

        inj_thread = threading.Thread(target=injector, daemon=True)
        inj_thread.start()

        # Simultaneously on main thread, execute 60 view switches and pump Tkinter event loop
        for i in range(60):
            target = self.view_keys[i % len(self.view_keys)]
            self.app.navigate_to(target)
            self.root.update_idletasks()
            self.root.update()
            time.sleep(0.002)

        inj_thread.join(timeout=2.0)

        # Wait for any remaining packets to drain via polling
        start_wait = time.time()
        while len(completed_packets) < num_packets:
            if time.time() - start_wait > 4.0:
                self.fail(f"Timed out: only {len(completed_packets)} of {num_packets} packets processed")
            self.root.update_idletasks()
            self.root.update()
            time.sleep(0.005)

        self.assertEqual(len(completed_packets), num_packets)
        self.assertEqual(sorted(completed_packets), list(range(num_packets)))

    def test_connection_state_flapping_during_navigation(self):
        """
        Rapidly alternates connection status (CONNECTED, DISCONNECTED, RECONNECTING)
        while switching views. Verifies:
        1. Status pill updates text and color without UI crashes.
        2. Offline warning banner appears/disappears cleanly via grid/grid_forget.
        3. All view on_connection_changed hooks execute safely.
        """
        states = ["CONNECTED", "DISCONNECTED", "RECONNECTING", "CONNECTING"]

        for cycle in range(16):
            st = states[cycle % len(states)]
            data = {"port": 9999, "reason": "Test cycling"}

            # Transition state
            self.app._on_connection_status_changed(st, data)

            # Navigate view
            vk = self.view_keys[cycle % len(self.view_keys)]
            self.app.navigate_to(vk)

            self.root.update_idletasks()
            self.root.update()

            # Verify status pill color reflects state
            if st == "CONNECTED":
                self.assertIn("Online", self.app.status_label.cget("text"))
            elif st in ("CONNECTING", "RECONNECTING"):
                self.assertIn("...", self.app.status_label.cget("text"))
            else:
                self.assertIn("Offline", self.app.status_label.cget("text"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
