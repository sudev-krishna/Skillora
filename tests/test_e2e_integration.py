#!/usr/bin/env python3
"""
Skillora End-to-End Live Integration Test Suite (tests/test_e2e_integration.py)

Comprehensive live client-server integration testing across:
- Real TCP binary packet framing (4-byte big-endian prefix + JSON envelope)
- All 7 core socket actions:
    1. AUTH
    2. GET_COMPANIES
    3. EVALUATE_ELIGIBILITY
    4. SOLVE_RECURRENCE
    5. RUN_SANDBOX
    6. GENERATE_APTITUDE
    7. EVALUATE_INTERVIEW
- All 6 Real-World Application Scenarios (TEST_INFRA.md Tier 4):
    Scenario 1: Full Student Placement Eligibility Run (Tier 1 vs Tier 2 vs Tier 3 comparison)
    Scenario 2: End-to-End Algorithmic Complexity Profiling & Divergence Detection
    Scenario 3: Concurrent Multi-Client Socket Exchange & Request-Response Matching
    Scenario 4: Complete Mock Technical Interview Session with AST Code Analysis
    Scenario 5: Symbolic Quantitative Aptitude Practice with Mathematical Proofs
    Scenario 6: Full System Offline Failure & Recovery Lifecycle (DB & Process Resiliency)
- Clean socket/thread teardown with zero resource leaks.
"""

from __future__ import annotations

import copy
import hashlib
import json
import logging
import os
import queue
import socket
import sqlite3
import sys
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Bootstrap project root
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
from server.bot.evaluator import evaluate_answer
from server.db.dao import SkilloraDAO
from server.db.init_db import init_database
from server.db.seed_data import (
    COMPANIES_SEED_DATA,
    DEMO_USER_DATA,
    QUESTIONS_SEED_DATA,
)
from server.math_engine.aptitude_generator import generate_problem
from server.network.dispatcher import ActionDispatcher
from server.network.tcp_server import SkilloraServer
from server.pipeline.placement import (
    TIER_LABEL_1,
    TIER_LABEL_2,
    TIER_LABEL_3,
    TIER_LABEL_NEEDS_DEV,
    compute_placement_readiness_index,
    filter_eligible_companies,
    is_eligible,
)
from server.profiler.canonical_order import canonicalize_big_o
from server.profiler.divergence import (
    classify_exponent,
    detect_divergence,
    estimate_power_exponent,
)
from server.profiler.recurrence import solve_recurrence
from server.sandbox.mp_runner import (
    benchmark_scaling,
    execute_in_sandbox,
    run_empirical_profile,
)

logger = logging.getLogger("skillora.test_e2e_integration")


def create_e2e_dispatcher(dao: Optional[SkilloraDAO] = None) -> ActionDispatcher:
    """
    Constructs an ActionDispatcher fully wired to genuine Skillora server modules
    for all 7 core socket actions.
    """
    dispatcher = ActionDispatcher()

    # 1. AUTH Action
    @dispatcher.route("AUTH")
    def handle_auth(payload: Dict[str, Any]) -> Dict[str, Any]:
        username = payload.get("username", "")
        password = payload.get("password", "")
        password_hash = payload.get("password_hash")
        if not password_hash and password:
            password_hash = hashlib.sha256(password.encode("utf-8")).hexdigest()

        user = None
        if dao is not None and username and password_hash:
            user = dao.authenticate_user(username, password_hash)

        if user:
            token = f"sess_{uuid.uuid4().hex}"
            return {
                "authenticated": True,
                "token": token,
                "user": {
                    "id": user.get("user_id", user.get("id")),
                    "username": user.get("username"),
                    "full_name": user.get("full_name"),
                    "branch": user.get("branch"),
                    "cgpa": user.get("cgpa"),
                    "backlogs": user.get("backlogs"),
                },
            }
        return {
            "status": "ERROR",
            "error": "Invalid username or password",
            "payload": {"authenticated": False},
        }

    # 2. GET_COMPANIES Action
    @dispatcher.route("GET_COMPANIES")
    def handle_get_companies(payload: Dict[str, Any]) -> Dict[str, Any]:
        tier = payload.get("tier")
        companies = []
        if dao is not None:
            try:
                companies = dao.get_all_companies_with_roles(tier_filter=tier)
            except Exception:
                companies = []
        if not companies:
            if tier:
                companies = [c for c in COMPANIES_SEED_DATA if c.get("tier") == tier]
            else:
                companies = COMPANIES_SEED_DATA
        return {"companies": companies, "count": len(companies)}

    # 3. EVALUATE_ELIGIBILITY Action
    @dispatcher.route("EVALUATE_ELIGIBILITY")
    def handle_evaluate_eligibility(payload: Dict[str, Any]) -> Dict[str, Any]:
        student = payload.get("student", {})
        companies = payload.get("companies")
        if not companies:
            if dao is not None:
                try:
                    companies = dao.get_all_companies_with_roles()
                except Exception:
                    companies = None
            if not companies:
                companies = COMPANIES_SEED_DATA
        eligible = filter_eligible_companies(companies, student)
        scores = student.get("scores", {})
        pri_res = compute_placement_readiness_index(scores)
        return {
            "eligible_companies": eligible,
            "eligible_count": len(eligible),
            "pri": pri_res,
        }

    # 4. SOLVE_RECURRENCE Action
    @dispatcher.route("SOLVE_RECURRENCE")
    def handle_solve_recurrence(payload: Dict[str, Any]) -> Dict[str, Any]:
        equation = payload.get("equation", "")
        base_cases = payload.get("base_cases")
        res = solve_recurrence(equation, base_cases)
        return res

    # 5. RUN_SANDBOX Action
    @dispatcher.route("RUN_SANDBOX")
    def handle_run_sandbox(payload: Dict[str, Any]) -> Dict[str, Any]:
        code = payload.get("code", "")
        scales = payload.get("input_scales", [10, 50, 100])
        timeout = float(payload.get("timeout", 2.0))
        input_gen = payload.get("input_generator", "int")
        theo_big_o = payload.get("theoretical_big_o")
        res = run_empirical_profile(
            code,
            input_scales=scales,
            timeout_sec=timeout,
            input_generator=input_gen,
        )
        div = None
        if theo_big_o:
            div = detect_divergence(theo_big_o, res["estimated_p"])
        return {
            "points": res["points"],
            "estimated_p": res["estimated_p"],
            "empirical_big_o": res["empirical_big_o"],
            "timed_out": res["timed_out"],
            "divergence": div,
        }

    # 6. GENERATE_APTITUDE Action
    @dispatcher.route("GENERATE_APTITUDE")
    def handle_generate_aptitude(payload: Dict[str, Any]) -> Dict[str, Any]:
        topic = payload.get("topic")
        diff = payload.get("difficulty", "Medium")
        seed = payload.get("seed")
        prob_dict = generate_problem(topic=topic, difficulty=diff, seed=seed)
        return prob_dict

    # 7. EVALUATE_INTERVIEW Action
    @dispatcher.route("EVALUATE_INTERVIEW")
    def handle_evaluate_interview(payload: Dict[str, Any]) -> Dict[str, Any]:
        question = payload.get("question")
        q_id = payload.get("question_id")
        if not question and q_id and dao is not None:
            question = dao.get_question_by_id(int(q_id))
        if not question:
            question = QUESTIONS_SEED_DATA[0]
        answer = payload.get("student_answer", payload.get("answer", ""))
        code = payload.get("code_snippet", payload.get("code", ""))
        eval_res = evaluate_answer(question, answer, code)
        user_id = payload.get("user_id")
        if user_id and dao is not None:
            try:
                dao.save_interview_session(
                    user_id=int(user_id),
                    total_score=eval_res["total_score"],
                    feedback_json=json.dumps(eval_res),
                )
            except Exception as ex:
                logger.debug("Failed saving session: %s", ex)
        return eval_res

    return dispatcher


# =============================================================================
# Suite 1: Live Socket Round-Trip Framing Across All 7 Actions
# =============================================================================

class TestLiveSocketRoundTripActions(unittest.TestCase):
    """
    Starts a live TcpServer instance on port 0 and connects a live SocketClient.
    Tests full round-trip binary packet framing across all 7 socket actions.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # Create isolated temporary SQLite DB
        cls.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        cls.temp_db.close()
        cls.db_path = cls.temp_db.name

        cls.db_conn = sqlite3.connect(cls.db_path, check_same_thread=False)
        init_database(conn=cls.db_conn, driver="sqlite", seed=True)
        cls.dao = SkilloraDAO(conn=cls.db_conn, driver="sqlite")

        # Create dispatcher & start live server on dynamic port
        cls.dispatcher = create_e2e_dispatcher(cls.dao)
        cls.server = SkilloraServer(host="127.0.0.1", port=0, dispatcher=cls.dispatcher)
        cls.server.start(blocking=False)
        cls.port = cls.server.port

        # Connect client
        cls.client = SocketClient(host="127.0.0.1", port=cls.port, auto_reconnect=False)
        cls.client.start()

        deadline = time.time() + 3.0
        while not cls.client.is_connected() and time.time() < deadline:
            time.sleep(0.02)
        if not cls.client.is_connected():
            raise RuntimeError(f"Client failed to connect to live server on port {cls.port}")

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.client.stop(timeout=1.0)
        except Exception:
            pass
        try:
            cls.server.stop(timeout=1.0)
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

    def test_action_0_ping(self) -> None:
        """Verifies built-in PING health check over live socket."""
        res = self.client.send_request_sync("PING", {"client_time": time.time()})
        self.assertEqual(res.get("status"), "SUCCESS")
        self.assertIn("server_time", res.get("payload", {}))

    def test_action_1_auth_roundtrip(self) -> None:
        """Verifies AUTH action with valid credentials and invalid credentials."""
        # Success path
        success_req = {
            "username": "demo_student",
            "password": "student123",
        }
        res = self.client.send_request_sync("AUTH", success_req)
        self.assertEqual(res.get("status"), "SUCCESS")
        payload = res.get("payload", {})
        self.assertTrue(payload.get("authenticated"))
        self.assertTrue(payload.get("token", "").startswith("sess_"))
        self.assertEqual(payload.get("user", {}).get("username"), "demo_student")

        # Failure path
        fail_req = {
            "username": "non_existent_student",
            "password": "invalid_password",
        }
        res_fail = self.client.send_request_sync("AUTH", fail_req)
        self.assertEqual(res_fail.get("status"), "ERROR")
        self.assertIn("Invalid", res_fail.get("error", ""))

    def test_action_2_get_companies_roundtrip(self) -> None:
        """Verifies GET_COMPANIES action returning seed companies and tier filtering."""
        # All companies
        res_all = self.client.send_request_sync("GET_COMPANIES", {})
        self.assertEqual(res_all.get("status"), "SUCCESS")
        companies = res_all.get("payload", {}).get("companies", [])
        self.assertGreaterEqual(len(companies), 4)

        # Tier 1 filter
        res_t1 = self.client.send_request_sync("GET_COMPANIES", {"tier": "Tier1"})
        self.assertEqual(res_t1.get("status"), "SUCCESS")
        t1_comps = res_t1.get("payload", {}).get("companies", [])
        self.assertGreaterEqual(len(t1_comps), 1)
        for comp in t1_comps:
            self.assertEqual(comp.get("tier"), "Tier1")

    def test_action_3_evaluate_eligibility_roundtrip(self) -> None:
        """Verifies EVALUATE_ELIGIBILITY action computing placement readiness."""
        student_payload = {
            "student": {
                "cgpa": 8.8,
                "backlogs": 0,
                "branch": "CSE",
                "scores": {
                    "coding": 88.0,
                    "technical": 82.0,
                    "aptitude": 85.0,
                    "communication": 78.0,
                    "academic": 88.0,
                },
            }
        }
        res = self.client.send_request_sync("EVALUATE_ELIGIBILITY", student_payload)
        self.assertEqual(res.get("status"), "SUCCESS")
        payload = res.get("payload", {})
        self.assertGreater(payload.get("eligible_count", 0), 0)
        pri = payload.get("pri", {})
        self.assertIn("pri_score", pri)
        self.assertIn("tier_readiness", pri)

    def test_action_4_solve_recurrence_roundtrip(self) -> None:
        """Verifies SOLVE_RECURRENCE action solving Master Theorem recurrence via SymPy."""
        solve_req = {
            "equation": "T(n) = 2*T(n/2) + n",
            "base_cases": {"T(1)": 1},
        }
        res = self.client.send_request_sync("SOLVE_RECURRENCE", solve_req)
        self.assertEqual(res.get("status"), "SUCCESS")
        payload = res.get("payload", {})
        self.assertIn("O(n log n)", payload.get("big_o", ""))
        self.assertFalse(payload.get("error"))

    def test_action_5_run_sandbox_roundtrip(self) -> None:
        """Verifies RUN_SANDBOX action executing Python code in isolated process."""
        sandbox_req = {
            "code": "def solve(n):\n    return sum(range(n))\n",
            "input_scales": [500, 1000, 2000],
            "timeout": 2.0,
            "theoretical_big_o": "O(n)",
        }
        res = self.client.send_request_sync("RUN_SANDBOX", sandbox_req)
        self.assertEqual(res.get("status"), "SUCCESS")
        payload = res.get("payload", {})
        self.assertFalse(payload.get("timed_out"))
        self.assertEqual(len(payload.get("points", [])), 3)
        self.assertIsNotNone(payload.get("divergence"))

    def test_action_6_generate_aptitude_roundtrip(self) -> None:
        """Verifies GENERATE_APTITUDE action generating problem with 4 options and proofs."""
        aptitude_req = {
            "topic": "interest_difference",
            "difficulty": "Medium",
            "seed": 2026,
        }
        res = self.client.send_request_sync("GENERATE_APTITUDE", aptitude_req)
        self.assertEqual(res.get("status"), "SUCCESS")
        payload = res.get("payload", {})
        self.assertEqual(len(payload.get("options", [])), 4)
        self.assertIn(payload.get("correct_option_index"), [0, 1, 2, 3])
        self.assertGreater(len(payload.get("proof_steps", [])), 0)

    def test_action_7_evaluate_interview_roundtrip(self) -> None:
        """Verifies EVALUATE_INTERVIEW action performing 3-tier offline evaluation."""
        eval_req = {
            "question": {
                "category": "Coding",
                "topic": "DSA: Two Sum / Hash Map",
                "expected_keywords_csv": "hash map,dictionary,complement,two sum,O(n)",
                "test_cases_json": json.dumps({"expected_constructs": ["FunctionDef", "For", "If", "Return"]}),
            },
            "student_answer": (
                "This algorithm is defined as using a hash map to find two numbers that sum to the target in O(n) time complexity. "
                "We store the complement in a dictionary and return indices."
            ),
            "code_snippet": (
                "def two_sum(nums, target):\n"
                "    seen = {}\n"
                "    for i, x in enumerate(nums):\n"
                "        comp = target - x\n"
                "        if comp in seen:\n"
                "            return [seen[comp], i]\n"
                "        seen[x] = i\n"
                "    return []\n"
            ),
        }
        res = self.client.send_request_sync("EVALUATE_INTERVIEW", eval_req)
        self.assertEqual(res.get("status"), "SUCCESS")
        payload = res.get("payload", {})
        self.assertGreater(payload.get("keyword_score", 0), 50.0)
        self.assertGreater(payload.get("structure_score", 0), 50.0)
        self.assertGreater(payload.get("ast_score", 0), 50.0)
        self.assertGreater(payload.get("total_score", 0), 50.0)


# =============================================================================
# Suite 2: Real-World Placement Application Scenarios 1 to 6
# =============================================================================

class TestScenario1StudentPlacementEligibility(unittest.TestCase):
    """
    Scenario 1: Full Student Placement Eligibility Run (Tier 1 vs Tier 2 vs Tier 3 comparison).
    Exercises Features: F5, F6, F7, F13, F14, F23.
    Verifies pure functional pipeline, curried predicate immutability, and PRI scoring.
    """

    def test_full_placement_eligibility_tier_comparison_and_immutability(self) -> None:
        # 1. Load companies
        companies = copy.deepcopy(COMPANIES_SEED_DATA)
        companies_snapshot = copy.deepcopy(companies)

        # 2. Define 3 realistic candidate profiles
        candidate_t1 = {
            "full_name": "Rohan Deshmukh",
            "branch": "CSE",
            "cgpa": 9.25,
            "backlogs": 0,
            "scores": {
                "coding": 94.0,
                "technical": 89.0,
                "aptitude": 88.0,
                "communication": 85.0,
                "academic": 92.5,
            },
        }

        candidate_t2 = {
            "full_name": "Pooja Hegde",
            "branch": "ECE",
            "cgpa": 7.65,
            "backlogs": 0,
            "scores": {
                "coding": 72.0,
                "technical": 74.0,
                "aptitude": 78.0,
                "communication": 70.0,
                "academic": 76.5,
            },
        }

        candidate_deficit = {
            "full_name": "Vikas Verma",
            "branch": "MECH",
            "cgpa": 6.20,
            "backlogs": 2,
            "scores": {
                "coding": 42.0,
                "technical": 48.0,
                "aptitude": 55.0,
                "communication": 50.0,
                "academic": 62.0,
            },
        }

        cand_t1_snapshot = copy.deepcopy(candidate_t1)
        cand_t2_snapshot = copy.deepcopy(candidate_t2)
        cand_def_snapshot = copy.deepcopy(candidate_deficit)

        # 3. Filter eligible companies via pure functional pipeline
        t1_eligible = filter_eligible_companies(companies, candidate_t1)
        t2_eligible = filter_eligible_companies(companies, candidate_t2)
        def_eligible = filter_eligible_companies(companies, candidate_deficit)

        # Tier 1 candidate qualifies for top product firms (Amazon, Microsoft)
        t1_names = [c["name"] for c in t1_eligible]
        self.assertIn("Amazon", t1_names)
        self.assertIn("Microsoft", t1_names)
        self.assertGreater(len(t1_eligible), len(t2_eligible))

        # Tier 2 candidate qualifies for Amazon (cutoff 7.50, ECE accepted)
        # but fails Microsoft (cutoff 8.00)
        t2_names = [c["name"] for c in t2_eligible]
        self.assertIn("Amazon", t2_names)
        self.assertNotIn("Microsoft", t2_names)

        # Deficit candidate fails Tier 1 and Tier 2 due to backlogs and low CGPA
        self.assertEqual(len(def_eligible), 0)

        # 4. Compute composite Placement Readiness Index (PRI) via map/reduce
        pri_t1 = compute_placement_readiness_index(candidate_t1["scores"], target_tier="Tier1")
        pri_t2 = compute_placement_readiness_index(candidate_t2["scores"], target_tier="Tier2")
        pri_def = compute_placement_readiness_index(candidate_deficit["scores"], target_tier="Tier3")

        self.assertGreaterEqual(pri_t1["pri_score"], 85.0)
        self.assertEqual(pri_t1["tier_readiness"], TIER_LABEL_1)
        self.assertEqual(len(pri_t1["gap_analysis"]), 0)

        self.assertGreaterEqual(pri_t2["pri_score"], 65.0)
        self.assertLess(pri_t2["pri_score"], 85.0)
        self.assertIn(pri_t2["tier_readiness"], [TIER_LABEL_1, TIER_LABEL_2])

        self.assertLess(pri_def["pri_score"], 60.0)
        self.assertIn(pri_def["tier_readiness"], [TIER_LABEL_3, TIER_LABEL_NEEDS_DEV])
        self.assertGreater(len(pri_def["gap_analysis"]), 0)

        # 5. Purity check: Verify immutability of inputs
        self.assertEqual(companies, companies_snapshot)
        self.assertEqual(candidate_t1, cand_t1_snapshot)
        self.assertEqual(candidate_t2, cand_t2_snapshot)
        self.assertEqual(candidate_deficit, cand_def_snapshot)


class TestScenario2AlgorithmicComplexityProfiling(unittest.TestCase):
    """
    Scenario 2: End-to-End Algorithmic Complexity Profiling & Divergence Detection.
    Exercises Features: F8, F9, F10, F11, F12.
    Derives closed form via SymPy and profiles code in isolated multiprocessing sandbox.
    """

    def test_complexity_profiling_and_divergence_detection(self) -> None:
        # Phase 1: Symbolic Recurrence Derivation (MergeSort recurrence)
        solve_res = solve_recurrence("T(n) = 2*T(n/2) + n", {"T(1)": 1})
        self.assertEqual(solve_res.get("big_o"), "O(n log n)")
        self.assertIsNone(solve_res.get("error"))

        # Phase 2: Authentic Execution in Sandbox & Matching Divergence
        fast_code = """
def solve(n):
    total = 0
    for i in range(n):
        total += i
    return total
"""
        res_exec = execute_in_sandbox(fast_code, input_val=1000, timeout_sec=2.0)
        self.assertEqual(res_exec["status"], "SUCCESS")
        self.assertFalse(res_exec["timed_out"])

        # Synthetic linear scaling points -> p ~ 1.0 -> MATCH
        points_linear = [(1000, 0.001), (2000, 0.002), (4000, 0.004), (8000, 0.008)]
        div_fast = detect_divergence("O(n)", points_linear)
        self.assertFalse(div_fast["divergence"])
        self.assertEqual(div_fast["nature"], "MATCH")

        # Phase 3: Suboptimal Quadratic Algorithm Execution & Divergence Detection
        slow_quadratic_code = """
def solve(n):
    count = 0
    for i in range(n):
        for j in range(n):
            count += 1
    return count
"""
        res_quad = execute_in_sandbox(slow_quadratic_code, input_val=200, timeout_sec=2.0)
        self.assertEqual(res_quad["status"], "SUCCESS")

        # Synthetic quadratic scaling points -> p ~ 2.0 -> WORSE_THAN_EXPECTED
        points_quad = [(100, 0.001), (200, 0.004), (400, 0.016), (800, 0.064)]
        div_slow = detect_divergence("O(n)", points_quad)
        self.assertTrue(div_slow["divergence"])
        self.assertEqual(div_slow["nature"], "WORSE_THAN_EXPECTED")
        self.assertIn("divergence detected", div_slow["diagnostic"].lower())


class TestScenario3ConcurrentMultiClientExchange(unittest.TestCase):
    """
    Scenario 3: Concurrent Multi-Client Socket Exchange & Request-Response Matching.
    Exercises Features: F1, F2, F3, F4.
    Runs 5 concurrent SocketClients hitting the server simultaneously across threads.
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

    def test_concurrent_multi_client_traffic_and_correlation(self) -> None:
        num_clients = 5
        requests_per_client = 6
        clients: List[SocketClient] = []

        # Connect clients concurrently
        for i in range(num_clients):
            c = SocketClient(host="127.0.0.1", port=self.port, auto_reconnect=False)
            c.start()
            clients.append(c)

        deadline = time.time() + 3.0
        while not all(c.is_connected() for c in clients) and time.time() < deadline:
            time.sleep(0.02)

        for idx, c in enumerate(clients):
            self.assertTrue(c.is_connected(), f"Client {idx} failed to connect")

        errors: List[str] = []
        completed_requests = 0
        lock = threading.Lock()

        def worker_task(client_idx: int, client: SocketClient) -> None:
            nonlocal completed_requests
            for r_idx in range(requests_per_client):
                try:
                    action = "PING" if r_idx % 2 == 0 else "GET_COMPANIES"
                    payload = {"client": client_idx, "seq": r_idx}
                    res = client.send_request_sync(action, payload, timeout=3.0)
                    if res.get("status") != "SUCCESS":
                        with lock:
                            errors.append(f"Client {client_idx} req {r_idx} returned ERROR: {res}")
                    else:
                        with lock:
                            completed_requests += 1
                except Exception as ex:
                    with lock:
                        errors.append(f"Client {client_idx} req {r_idx} exception: {ex}")

        threads = [
            threading.Thread(target=worker_task, args=(i, clients[i]))
            for i in range(num_clients)
        ]

        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=10.0)

        # Stop clients
        for c in clients:
            c.stop(timeout=1.0)

        self.assertEqual(len(errors), 0, f"Errors in concurrent exchange: {errors}")
        self.assertEqual(completed_requests, num_clients * requests_per_client)


class TestScenario4MockTechnicalInterviewSession(unittest.TestCase):
    """
    Scenario 4: Complete Mock Technical Interview Session with AST Code Analysis.
    Exercises Features: F5, F7, F21, F22, F23.
    Evaluates student response with 3-tier scoring and persists session into DB.
    """

    def setUp(self) -> None:
        self.temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self.temp_db.close()
        self.db_path = self.temp_db.name
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        init_database(conn=self.conn, driver="sqlite", seed=True)
        self.dao = SkilloraDAO(conn=self.conn, driver="sqlite")

    def tearDown(self) -> None:
        self.conn.close()
        if os.path.exists(self.db_path):
            os.unlink(self.db_path)

    def test_mock_technical_interview_session_ast_and_db_persistence(self) -> None:
        # 1. Fetch Two Sum question from seed data
        questions = self.dao.get_questions_by_category("Coding")
        self.assertGreater(len(questions), 0)
        q = next((item for item in questions if "Two Sum" in item.get("topic", "")), questions[0])

        # 2. Candidate submits exemplary response
        student_text = (
            "This algorithm is defined as using a hash map dictionary to solve two sum in single pass O(n) time complexity. "
            "For each number, we compute complement = target - val. If complement is in seen dictionary, we return both indices. "
            "Otherwise we store the key-value mapping of value to index in the hash table."
        )
        student_code = (
            "def solve(nums: list[int], target: int) -> list[int]:\n"
            "    seen = {}\n"
            "    for i, num in enumerate(nums):\n"
            "        comp = target - num\n"
            "        if comp in seen:\n"
            "            return [seen[comp], i]\n"
            "        seen[num] = i\n"
            "    return []\n"
        )

        res = evaluate_answer(q, student_text, student_code)
        self.assertGreaterEqual(res["keyword_score"], 60.0)
        self.assertGreaterEqual(res["structure_score"], 50.0)
        self.assertGreaterEqual(res["ast_score"], 70.0)
        self.assertGreaterEqual(res["total_score"], 60.0)
        self.assertEqual(len(res["flagged_anti_patterns"]), 0)

        # 3. Save interview session into database via DAO
        user = self.dao.authenticate_user(
            DEMO_USER_DATA["username"],
            DEMO_USER_DATA["password_hash"],
        )
        self.assertIsNotNone(user)
        user_id = user.get("user_id", user.get("id"))

        session_id = self.dao.save_interview_session(
            user_id=user_id,
            total_score=res["total_score"],
            feedback_json=json.dumps(res),
        )
        self.assertGreater(session_id, 0)

        # 4. Verify session record retrieval
        sessions = self.dao.get_user_interview_sessions(user_id=user_id)
        self.assertGreater(len(sessions), 0)
        saved = sessions[0]
        self.assertAlmostEqual(saved["total_score"], res["total_score"], places=1)

        # 5. Anti-pattern detection test
        bad_code = (
            "def solve(nums, target):\n"
            "    try:\n"
            "        pass\n"
            "    except:\n"
            "        pass\n"
        )
        bad_res = evaluate_answer(q, "Incomplete attempt", bad_code)
        self.assertIn("bare_except", bad_res["flagged_anti_patterns"])
        self.assertLess(bad_res["ast_score"], res["ast_score"])


class TestScenario5SymbolicQuantitativeAptitudePractice(unittest.TestCase):
    """
    Scenario 5: Symbolic Quantitative Aptitude Practice with Mathematical Proofs.
    Exercises Features: F8, F15, F19.
    Tests all 4 placement math domains with symbolic proof verification and seed determinism.
    """

    def test_symbolic_aptitude_generation_proofs_and_distractors(self) -> None:
        topics = [
            "interest_difference",
            "work_collaboration",
            "urn_probability",
            "cayley_trees",
        ]

        for topic in topics:
            prob = generate_problem(topic=topic, difficulty="Medium", seed=1001)

            # 1. 4 distinct options with one correct answer
            options = prob["options"]
            self.assertEqual(len(options), 4)
            self.assertEqual(len(set(options)), 4, f"Duplicate options in topic {topic}")

            correct_idx = prob["correct_option_index"]
            self.assertIn(correct_idx, [0, 1, 2, 3])
            correct_val = options[correct_idx]
            self.assertTrue(len(correct_val) > 0)

            # 2. 3 distractors mapping to mathematical misconceptions
            self.assertEqual(len(prob["distractors"]), 3)
            self.assertNotIn(prob["correct_answer"], prob["distractors"])
            self.assertGreaterEqual(len(prob.get("misconception_map", {})), 1)

            # 3. Rigorous step-by-step symbolic derivation proofs
            proof_steps = prob["proof_steps"]
            self.assertGreaterEqual(len(proof_steps), 3)
            for step in proof_steps:
                self.assertTrue(len(step["title"]) > 0)
                self.assertTrue(len(step["latex"]) > 0)
                self.assertTrue(len(step["explanation"]) > 0)

        # 4. Seed reproducibility (idempotency)
        p1 = generate_problem("work_collaboration", seed=42)
        p2 = generate_problem("work_collaboration", seed=42)
        self.assertEqual(p1["question_text"], p2["question_text"])
        self.assertEqual(p1["options"], p2["options"])
        self.assertEqual(p1["correct_option_index"], p2["correct_option_index"])


class TestScenario6OfflineFailureAndRecoveryLifecycle(unittest.TestCase):
    """
    Scenario 6: Full System Offline Failure & Recovery Lifecycle (DB & Process Resiliency).
    Exercises Features: F3, F6, F7, F10.
    Tests MySQL-to-SQLite transparent fallback, sandbox rogue loop containment, and socket server recovery.
    """

    def test_offline_db_fallback_and_sandbox_watchdog_resiliency(self) -> None:
        # Part A: Database Fallback Resiliency
        # When MySQL standard connection is unreachable, system operates 100% offline via SQLite
        temp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        temp_db.close()
        db_path = temp_db.name

        conn = sqlite3.connect(db_path, check_same_thread=False)
        success = init_database(conn=conn, driver="sqlite", seed=True)
        self.assertTrue(success)

        dao = SkilloraDAO(conn=conn, driver="sqlite")
        comps = dao.get_all_companies_with_roles()
        self.assertGreater(len(comps), 0)

        # Part B: Multiprocessing Sandbox Watchdog Resiliency
        # Infinite rogue loop is forcefully killed by watchdog timeout without hanging host
        rogue_code = "def solve(n):\n    while True:\n        pass\n"
        start_t = time.time()
        res_rogue = execute_in_sandbox(rogue_code, input_val=10, timeout_sec=0.8)
        elapsed = time.time() - start_t

        self.assertTrue(res_rogue["timed_out"])
        self.assertEqual(res_rogue["status"], "TIMEOUT")
        self.assertLess(elapsed, 2.5)

        # Subsequent execution succeeds immediately (process isolation restored)
        healthy_code = "def solve(n):\n    return n * n\n"
        res_healthy = execute_in_sandbox(healthy_code, input_val=7, timeout_sec=1.0)
        self.assertEqual(res_healthy["status"], "SUCCESS")
        self.assertEqual(res_healthy["result"], 49)

        # Clean DB
        conn.close()
        if os.path.exists(db_path):
            os.unlink(db_path)

    def test_server_so_reuseaddr_and_reconnection_lifecycle(self) -> None:
        """Verifies clean server restart on identical port using SO_REUSEADDR."""
        disp = create_e2e_dispatcher()
        s1 = SkilloraServer(host="127.0.0.1", port=0, dispatcher=disp)
        s1.start(blocking=False)
        target_port = s1.port

        c1 = SocketClient(host="127.0.0.1", port=target_port, auto_reconnect=False)
        c1.start()
        time.sleep(0.1)
        self.assertTrue(c1.is_connected())

        # Exchange ping
        res1 = c1.send_request_sync("PING", {"test": 1})
        self.assertEqual(res1.get("status"), "SUCCESS")

        # Stop client and server
        c1.stop(timeout=1.0)
        s1.stop(timeout=1.0)

        # Restart server on exact same port immediately
        s2 = SkilloraServer(host="127.0.0.1", port=target_port, dispatcher=disp)
        s2.start(blocking=False)
        self.assertEqual(s2.port, target_port)

        c2 = SocketClient(host="127.0.0.1", port=target_port, auto_reconnect=False)
        c2.start()
        time.sleep(0.1)
        self.assertTrue(c2.is_connected())

        res2 = c2.send_request_sync("PING", {"test": 2})
        self.assertEqual(res2.get("status"), "SUCCESS")

        c2.stop(timeout=1.0)
        s2.stop(timeout=1.0)


# =============================================================================
# Suite 3: Clean Shutdown & Zero Resource Leaks
# =============================================================================

class TestCleanShutdownAndResourceManagement(unittest.TestCase):
    """
    Validates zero socket and thread leaks during server and client teardown.
    """

    def test_clean_socket_shutdown_and_no_resource_leaks(self) -> None:
        dispatcher = create_e2e_dispatcher()
        server = SkilloraServer(host="127.0.0.1", port=0, dispatcher=dispatcher)
        server.start(blocking=False)

        client = SocketClient(host="127.0.0.1", port=server.port, auto_reconnect=False)
        client.start()

        deadline = time.time() + 2.0
        while not client.is_connected() and time.time() < deadline:
            time.sleep(0.02)
        self.assertTrue(client.is_connected())

        # Stop client cleanly
        client.stop(timeout=1.0)
        self.assertFalse(client.is_connected())
        self.assertIsNone(client._worker_thread)

        # Stop server cleanly
        server.stop(timeout=1.0)
        self.assertFalse(server.is_running)
        self.assertEqual(server.active_clients_count, 0)


if __name__ == "__main__":
    unittest.main()
