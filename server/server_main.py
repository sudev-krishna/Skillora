"""
Skillora Server Entry Point (server/server_main.py)
Orchestrates database initialization, route dispatching, and multi-client TCP server.
Zero third-party web frameworks (standard library + local modules only).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
from pathlib import Path
import signal
import sys
import time
import uuid
from typing import Any, Dict, Optional

# Bootstrap project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.bot.evaluator import evaluate_answer
from server.db.dao import SkilloraDAO
from server.db.init_db import init_database
from server.db.seed_data import (
    COMPANIES_SEED_DATA,
    QUESTIONS_SEED_DATA,
)
from server.math_engine.aptitude_generator import generate_problem
from server.network.dispatcher import ActionDispatcher
from server.network.tcp_server import SkilloraServer
from server.pipeline.placement import (
    compute_placement_readiness_index,
    filter_eligible_companies,
)
from server.profiler.divergence import detect_divergence
from server.profiler.recurrence import solve_recurrence
from server.sandbox.mp_runner import run_empirical_profile

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("skillora.server_main")


def build_server_dispatcher(dao: Optional[SkilloraDAO] = None) -> ActionDispatcher:
    """Builds and wires the 7 core socket action routes to genuine backend modules."""
    dispatcher = ActionDispatcher()

    # 1. AUTH
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

    # 2. GET_COMPANIES
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

    # 3. EVALUATE_ELIGIBILITY
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

    # 4. SOLVE_RECURRENCE
    @dispatcher.route("SOLVE_RECURRENCE")
    def handle_solve_recurrence(payload: Dict[str, Any]) -> Dict[str, Any]:
        equation = payload.get("equation", "")
        base_cases = payload.get("base_cases")
        return solve_recurrence(equation, base_cases)

    # 5. RUN_SANDBOX
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

    # 6. GENERATE_APTITUDE
    @dispatcher.route("GENERATE_APTITUDE")
    def handle_generate_aptitude(payload: Dict[str, Any]) -> Dict[str, Any]:
        topic = payload.get("topic")
        diff = payload.get("difficulty", "Medium")
        seed = payload.get("seed")
        return generate_problem(topic=topic, difficulty=diff, seed=seed)

    # 7. EVALUATE_INTERVIEW
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Skillora Server Daemon")
    parser.add_argument("--host", default="0.0.0.0", help="Host address to bind (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=9999, help="TCP port to listen on (default: 9999)")
    parser.add_argument("--seed", action="store_true", default=True, help="Seed database on startup")
    args = parser.parse_args()

    logger.info("Initializing Skillora database...")
    init_database(seed=args.seed)
    dao = SkilloraDAO()

    dispatcher = build_server_dispatcher(dao)
    server = SkilloraServer(host=args.host, port=args.port, dispatcher=dispatcher)

    def handle_signal(sig, frame):
        logger.info("Shutdown signal received. Stopping server...")
        server.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)

    logger.info(f"Starting Skillora Server on {args.host}:{args.port}...")
    server.start(blocking=True)


if __name__ == "__main__":
    main()
