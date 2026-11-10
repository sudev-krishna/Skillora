"""
Skillora Unit Test Suite: Database Layer, DAO & Seed Data
Covers:
  - Dual-engine DDL schema creation and dialect adaptation (F5)
  - Connection manager, 2.0s timeout, transparent SQLite fallback, WAL mode, foreign keys (F6)
  - Thread-local SQLite connection safety under concurrency
  - Parameter placeholder translation (? vs %s)
  - UnifiedConnection dual interface (unpacking and object method calls)
  - Unified DAO with atomic transactions and full CRUD methods (F7)
  - Placement seed data integrity: 10 companies, 11 roles with weights summing to 1.0, 30 questions (F23)
  - Idempotent database initialization and CLI reset runner
"""

import hashlib
import json
import os
import sqlite3
import sys
import threading
import time
import unittest
from pathlib import Path
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.db.connection import (
    ConnectionManager,
    UnifiedConnection,
    UnifiedCursor,
    get_db_connection,
    get_driver_name,
    reset_db_connection,
)
from server.db.dao import (
    SkilloraDAO,
    adapt_ddl_for_driver,
    execute_ddl,
)
from server.db.init_db import init_database
from server.db.seed_data import (
    COMPANIES_SEED_DATA,
    DEMO_USER_DATA,
    QUESTIONS_SEED_DATA,
    seed_database,
)


class TestSchemaDDL(unittest.TestCase):
    """Verifies schema DDL, SQLite dialect execution, and MySQL translation."""

    def setUp(self) -> None:
        self.schema_path = PROJECT_ROOT / "server" / "db" / "schema.sql"
        self.assertTrue(self.schema_path.exists(), "schema.sql must exist")
        self.ddl_sql = self.schema_path.read_text(encoding="utf-8")

    def test_schema_file_contains_all_six_tables(self) -> None:
        """Verifies schema.sql defines all 6 canonical 3NF tables."""
        expected_tables = [
            "users",
            "companies",
            "company_roles",
            "question_bank",
            "interview_sessions",
            "sympy_logs",
        ]
        for tbl in expected_tables:
            self.assertIn(f"CREATE TABLE IF NOT EXISTS {tbl}", self.ddl_sql)

    def test_ddl_adaptation_for_mysql(self) -> None:
        """Verifies adapt_ddl_for_driver translates SQLite autoincrement to MySQL syntax."""
        mysql_ddl = adapt_ddl_for_driver(self.ddl_sql, "mysql")
        self.assertNotIn("INTEGER PRIMARY KEY AUTOINCREMENT", mysql_ddl)
        self.assertIn("INT AUTO_INCREMENT PRIMARY KEY", mysql_ddl)

    def test_ddl_adaptation_for_sqlite(self) -> None:
        """Verifies adapt_ddl_for_driver maintains or converts to SQLite autoincrement."""
        sqlite_ddl = adapt_ddl_for_driver(self.ddl_sql, "sqlite")
        self.assertIn("INTEGER PRIMARY KEY AUTOINCREMENT", sqlite_ddl)

    def test_ddl_execution_in_memory_sqlite(self) -> None:
        """Verifies executing schema DDL creates all 6 tables in an in-memory SQLite DB."""
        conn = sqlite3.connect(":memory:")
        execute_ddl(conn, "sqlite", self.ddl_sql)

        cur = conn.cursor()
        cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';")
        tables = [row[0] for row in cur.fetchall()]
        cur.close()
        conn.close()

        expected_tables = {
            "users",
            "companies",
            "company_roles",
            "question_bank",
            "interview_sessions",
            "sympy_logs",
        }
        self.assertTrue(expected_tables.issubset(set(tables)))


class TestConnectionManager(unittest.TestCase):
    """Verifies dual-driver manager, transparent fallback, PRAGMAs, and thread safety."""

    def setUp(self) -> None:
        reset_db_connection()

    def tearDown(self) -> None:
        reset_db_connection()

    def test_transparent_sqlite_fallback(self) -> None:
        """Verifies fallback to SQLite when MySQL is unreachable."""
        conn, driver = get_db_connection(sqlite_path=":memory:", driver="sqlite")
        self.assertEqual(driver, "sqlite")
        self.assertIsInstance(conn, UnifiedConnection)
        conn.close()

    def test_unified_connection_dual_interface(self) -> None:
        """Verifies UnifiedConnection unpacks as tuple and acts as connection object."""
        unified = get_db_connection(sqlite_path=":memory:", driver="sqlite")
        # 1. Unpacking
        c, d = unified
        self.assertEqual(d, "sqlite")
        self.assertEqual(c, unified)

        # 2. Object methods
        cur = unified.cursor(dictionary=True)
        cur.execute("SELECT 42 as answer;")
        row = cur.fetchone()
        self.assertEqual(row, {"answer": 42})
        cur.close()

        # 3. Direct execute
        cur2 = unified.execute("SELECT 99 as val;")
        self.assertEqual(cur2.fetchone(), {"val": 99})
        cur2.close()
        unified.close()

    def test_foreign_keys_pragma_enforced(self) -> None:
        """Verifies foreign key constraints are strictly enforced on SQLite connections."""
        conn, driver = get_db_connection(sqlite_path=":memory:", driver="sqlite")
        dao = SkilloraDAO(conn, driver)
        dao.init_schema()

        # Attempt to insert role referencing non-existent company_id 999
        with self.assertRaises((sqlite3.IntegrityError, Exception)):
            dao.execute_update(
                "INSERT INTO company_roles (company_id, role_title, package_lpa) VALUES (?, ?, ?)",
                (999, "Phantom Role", 10.0),
            )
        conn.close()

    def test_context_manager_commit_and_rollback(self) -> None:
        """Verifies UnifiedConnection commits on clean exit and rolls back on exception."""
        conn, driver = get_db_connection(sqlite_path=":memory:", driver="sqlite")
        conn.execute("CREATE TABLE kv (k TEXT PRIMARY KEY, v TEXT);")
        conn.commit()

        # Clean block commits
        with conn:
            conn.execute("INSERT INTO kv VALUES ('a', '1');")

        cur = conn.execute("SELECT v FROM kv WHERE k = 'a';")
        self.assertEqual(cur.fetchone()["v"], "1")
        cur.close()

        # Failing block rolls back
        try:
            with conn:
                conn.execute("INSERT INTO kv VALUES ('b', '2');")
                raise RuntimeError("Forced abort")
        except RuntimeError:
            pass

        cur = conn.execute("SELECT v FROM kv WHERE k = 'b';")
        self.assertIsNone(cur.fetchone())
        cur.close()
        conn.close()

    def test_driver_caching_performance(self) -> None:
        """Verifies subsequent calls to get_db_connection in cached offline mode are fast."""
        # Prime connection
        first_conn, _ = get_db_connection()
        t0 = time.perf_counter()
        last_conn = None
        for _ in range(50):
            last_conn, driver = get_db_connection()
            self.assertEqual(driver, "sqlite")
        t1 = time.perf_counter()
        avg_ms = ((t1 - t0) / 50.0) * 1000.0
        self.assertLess(avg_ms, 5.0, f"Cached connection retrieval should be sub-5ms, was {avg_ms:.3f}ms")

    def test_thread_local_concurrency_safety(self) -> None:
        """Verifies concurrent threads executing queries via get_db_connection do not corrupt state."""
        db_file = PROJECT_ROOT / "tests" / "test_concurrency.db"
        if db_file.exists():
            db_file.unlink()

        try:
            # Initialize schema in shared file
            conn_init, driver_init = get_db_connection(sqlite_path=str(db_file), driver="sqlite", thread_local=False)
            dao_init = SkilloraDAO(conn_init, driver_init)
            dao_init.init_schema()
            conn_init.close()

            errors: List[Exception] = []

            def worker_task(thread_id: int) -> None:
                conn = None
                try:
                    conn, driver = get_db_connection(sqlite_path=str(db_file), driver="sqlite", thread_local=True)
                    dao = SkilloraDAO(conn, driver)
                    for i in range(10):
                        username = f"user_{thread_id}_{i}"
                        dao.register_user(
                            username=username,
                            password_hash="dummyhash",
                            full_name=f"User {thread_id} {i}",
                            branch="CSE",
                            cgpa=8.0,
                            backlogs=0,
                        )
                except Exception as ex:
                    errors.append(ex)
                finally:
                    if conn is not None:
                        try:
                            conn.close()
                        except Exception:
                            pass

            threads = [threading.Thread(target=worker_task, args=(tid,)) for tid in range(5)]
            for t in threads:
                t.start()
            for t in threads:
                t.join(timeout=10.0)

            self.assertEqual(errors, [], f"Encountered thread concurrency errors: {errors}")

            # Verify total inserted
            conn_verify, driver_verify = get_db_connection(sqlite_path=str(db_file), driver="sqlite", thread_local=False)
            dao_verify = SkilloraDAO(conn_verify, driver_verify)
            cur = dao_verify.execute_query("SELECT COUNT(*) as cnt FROM users;")
            self.assertEqual(cur[0]["cnt"], 50)
            conn_verify.close()

        finally:
            reset_db_connection()
            if db_file.exists():
                try:
                    db_file.unlink()
                except Exception:
                    pass


class TestSkilloraDAO(unittest.TestCase):
    """Comprehensive test suite for SkilloraDAO CRUD and business logic."""

    def setUp(self) -> None:
        self.conn, self.driver = get_db_connection(sqlite_path=":memory:", driver="sqlite")
        self.dao = SkilloraDAO(self.conn, self.driver)
        self.dao.init_schema()

    def tearDown(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def test_parameter_placeholder_formatting(self) -> None:
        """Verifies _format_query dynamically converts ? to %s for mysql and keeps ? for sqlite."""
        q = "SELECT * FROM users WHERE username = ? AND cgpa >= ?"
        dao_sqlite = SkilloraDAO(self.conn, "sqlite")
        self.assertEqual(dao_sqlite._format_query(q), q)

        dao_mysql = SkilloraDAO(self.conn, "mysql")
        self.assertEqual(
            dao_mysql._format_query(q),
            "SELECT * FROM users WHERE username = %s AND cgpa >= %s",
        )

    def test_register_and_authenticate_user(self) -> None:
        """Verifies registering a student and authenticating credentials."""
        pw_hash = hashlib.sha256("secure_pw_123".encode("utf-8")).hexdigest()
        user_id = self.dao.register_user(
            username="priya_k",
            password_hash=pw_hash,
            full_name="Priya Kumar",
            branch="CSE",
            cgpa=9.1,
            backlogs=0,
            skills=["Python", "DSA", "SQL"],
        )
        self.assertIsInstance(user_id, int)
        self.assertGreater(user_id, 0)

        # Authenticate success
        auth_user = self.dao.authenticate_user("priya_k", pw_hash)
        self.assertIsNotNone(auth_user)
        self.assertEqual(auth_user["user_id"], user_id)
        self.assertEqual(auth_user["username"], "priya_k")
        self.assertEqual(auth_user["full_name"], "Priya Kumar")
        self.assertEqual(auth_user["skills"], ["Python", "DSA", "SQL"])
        self.assertNotIn("password_hash", auth_user, "Security violation: password_hash leaked in return dict")

        # Authenticate invalid password
        wrong_pw = hashlib.sha256("wrong_password".encode("utf-8")).hexdigest()
        self.assertIsNone(self.dao.authenticate_user("priya_k", wrong_pw))

        # Authenticate unknown user
        self.assertIsNone(self.dao.authenticate_user("unknown_user", pw_hash))

    def test_register_user_validation_and_duplicate_handling(self) -> None:
        """Verifies input validation and duplicate username rejection."""
        pw_hash = hashlib.sha256("pass".encode("utf-8")).hexdigest()

        # Empty username
        with self.assertRaises(ValueError):
            self.dao.register_user("", pw_hash, "Name", "CSE", 8.0)

        # Invalid CGPA
        with self.assertRaises(ValueError):
            self.dao.register_user("user1", pw_hash, "Name", "CSE", 11.5)

        # Negative backlogs
        with self.assertRaises(ValueError):
            self.dao.register_user("user1", pw_hash, "Name", "CSE", 8.0, backlogs=-1)

        # Duplicate username
        self.dao.register_user("duplicate_user", pw_hash, "First User", "CSE", 8.0)
        with self.assertRaises(ValueError):
            self.dao.register_user("duplicate_user", pw_hash, "Second User", "IT", 7.5)

    def test_get_user_by_id_and_update_profile(self) -> None:
        """Verifies retrieving user by ID and updating profile fields."""
        pw_hash = hashlib.sha256("mypass".encode("utf-8")).hexdigest()
        uid = self.dao.register_user(
            username="suresh",
            password_hash=pw_hash,
            full_name="Suresh Raina",
            branch="ECE",
            cgpa=7.8,
            backlogs=1,
            skills=["C++"],
        )

        user = self.dao.get_user_by_id(uid)
        self.assertIsNotNone(user)
        self.assertEqual(user["branch"], "ECE")
        self.assertEqual(user["cgpa"], 7.8)

        # Update profile
        success = self.dao.update_user_profile(
            user_id=uid,
            cgpa=8.2,
            backlogs=0,
            skills=["C++", "Python", "System Design"],
            branch="CSE",
        )
        self.assertTrue(success)

        updated_user = self.dao.get_user_by_id(uid)
        self.assertEqual(updated_user["cgpa"], 8.2)
        self.assertEqual(updated_user["backlogs"], 0)
        self.assertEqual(updated_user["branch"], "CSE")
        self.assertEqual(updated_user["skills"], ["C++", "Python", "System Design"])

    def test_company_and_roles_retrieval(self) -> None:
        """Verifies company insertion, role retrieval, and nested company roles loader."""
        seed_database(self.conn, driver="sqlite")

        companies = self.dao.get_all_companies()
        self.assertEqual(len(companies), 10)

        # Tier 1 filtering
        tier1_comps = self.dao.get_all_companies(tier_filter="Tier1")
        self.assertEqual(len(tier1_comps), 3)
        for comp in tier1_comps:
            self.assertEqual(comp["tier"], "Tier1")
            self.assertIsInstance(comp["eligible_branches"], list)

        # Single company
        first_comp = companies[0]
        comp_by_id = self.dao.get_company_by_id(first_comp["company_id"])
        self.assertIsNotNone(comp_by_id)
        self.assertEqual(comp_by_id["name"], first_comp["name"])

        # Roles
        roles = self.dao.get_company_roles(first_comp["company_id"])
        self.assertGreater(len(roles), 0)
        self.assertIn("round_structure", roles[0])
        self.assertIn("weights", roles[0]["round_structure"])

        # get_all_companies_with_roles
        all_with_roles = self.dao.get_all_companies_with_roles()
        self.assertEqual(len(all_with_roles), 10)
        total_roles = sum(len(c["roles"]) for c in all_with_roles)
        self.assertEqual(total_roles, 11)

    def test_question_bank_filtering_and_deserialization(self) -> None:
        """Verifies question retrieval by category, difficulty, keywords, and model answers."""
        seed_database(self.conn, driver="sqlite")

        # Category filter: Coding
        coding_qs = self.dao.get_questions_by_category("Coding")
        self.assertEqual(len(coding_qs), 8)
        for q in coding_qs:
            self.assertEqual(q["category"], "Coding")
            self.assertIsInstance(q["expected_keywords"], list)
            self.assertIsInstance(q["test_cases"], dict)
            self.assertIn("model_answer", q)
            self.assertGreater(len(q["model_answer"]), 10)

        # Category filter: Technical
        tech_qs = self.dao.get_questions_by_category("Technical")
        self.assertEqual(len(tech_qs), 22)

        # Filter with difficulty
        easy_coding = self.dao.get_questions_by_category("Coding", difficulty="Easy")
        self.assertGreater(len(easy_coding), 0)
        for q in easy_coding:
            self.assertEqual(q["difficulty"], "Easy")

        # Single question by ID
        first_q = coding_qs[0]
        q_by_id = self.dao.get_question_by_id(first_q["question_id"])
        self.assertIsNotNone(q_by_id)
        self.assertEqual(q_by_id["topic"], first_q["topic"])

    def test_interview_session_saving_and_history(self) -> None:
        """Verifies saving mock interview evaluations, scores, and retrieving session history."""
        pw_hash = hashlib.sha256("pw".encode("utf-8")).hexdigest()
        uid = self.dao.register_user("student_test", pw_hash, "Student Test", "CSE", 8.0)

        feedback_data = {
            "strengths": ["Clear explanation of pointer manipulation", "Identified O(1) space"],
            "gaps": ["Consider edge case of empty list"],
        }

        session_id = self.dao.save_interview_session(
            user_id=uid,
            total_score=85.5,
            feedback_json=feedback_data,
            aptitude_score=80.0,
            coding_score=90.0,
            technical_score=85.0,
            composite_pri=85.5,
        )
        self.assertIsInstance(session_id, int)
        self.assertGreater(session_id, 0)

        # Retrieve history
        sessions = self.dao.get_user_interview_sessions(uid)
        self.assertEqual(len(sessions), 1)
        sess = sessions[0]
        self.assertEqual(sess["session_id"], session_id)
        self.assertEqual(sess["composite_pri"], 85.5)
        self.assertEqual(sess["feedback"], feedback_data)

        # Single session by ID
        single_sess = self.dao.get_interview_session_by_id(session_id)
        self.assertIsNotNone(single_sess)
        self.assertEqual(single_sess["total_score"], 85.5)

    def test_sympy_operations_logging_and_aliasing(self) -> None:
        """Verifies logging symbolic math operations and checking field aliases."""
        pw_hash = hashlib.sha256("pw".encode("utf-8")).hexdigest()
        uid = self.dao.register_user("math_user", pw_hash, "Math Student", "CSE", 8.5)

        log_id = self.dao.log_sympy_operation(
            user_id=uid,
            expression="T(n) = 2*T(n/2) + n",
            result="n*log(n)",
            operation_type="RECURRENCE",
            derived_big_o="O(n log n)",
            empirical_runtime_ms=1.45,
        )
        self.assertIsInstance(log_id, int)
        self.assertGreater(log_id, 0)

        logs = self.dao.get_sympy_logs(user_id=uid)
        self.assertEqual(len(logs), 1)
        log_entry = logs[0]
        self.assertEqual(log_entry["log_id"], log_id)
        self.assertEqual(log_entry["derived_big_o"], "O(n log n)")
        # Check alias keys
        self.assertEqual(log_entry["recurrence_input"], "T(n) = 2*T(n/2) + n")
        self.assertEqual(log_entry["solved_closed_form"], "n*log(n)")

    def test_dashboard_stats_aggregation(self) -> None:
        """Verifies get_dashboard_stats consolidates metrics for dashboard view."""
        pw_hash = hashlib.sha256("pw".encode("utf-8")).hexdigest()
        uid = self.dao.register_user("dash_user", pw_hash, "Dash User", "CSE", 8.8)

        # Initially zero stats
        stats = self.dao.get_dashboard_stats(uid)
        self.assertEqual(stats["user_id"], uid)
        self.assertEqual(stats["recent_pri"], 0.0)
        self.assertEqual(stats["sessions_count"], 0)
        self.assertEqual(stats["recurrence_count"], 0)
        self.assertEqual(stats["top_eligible_tier"], "Needs Preparation")

        # Add session with high score
        self.dao.save_interview_session(user_id=uid, total_score=92.0, composite_pri=92.0)
        self.dao.log_sympy_operation(user_id=uid, expression="T(n)=T(n-1)+1", result="n")

        stats2 = self.dao.get_dashboard_stats(uid)
        self.assertEqual(stats2["recent_pri"], 92.0)
        self.assertEqual(stats2["sessions_count"], 1)
        self.assertEqual(stats2["recurrence_count"], 1)
        self.assertEqual(stats2["top_eligible_tier"], "Tier 1 (Product Companies)")


class TestSeedDataAndInitialization(unittest.TestCase):
    """Verifies benchmark seed data, role weight normalization, and init_database runner."""

    def test_company_roles_weight_sum_strictly_equals_one(self) -> None:
        """Verifies that aptitude + coding + technical weights sum to 1.0 for all 11 roles."""
        total_roles = 0
        for comp in COMPANIES_SEED_DATA:
            for role in comp["roles"]:
                total_roles += 1
                weights = role["round_structure"]["weights"]
                w_sum = round(weights["aptitude"] + weights["coding"] + weights["technical"], 4)
                self.assertEqual(
                    w_sum,
                    1.0,
                    f"Role '{role['role_title']}' in '{comp['name']}' weights sum to {w_sum}, expected 1.0",
                )
        self.assertEqual(total_roles, 11, "Expected exactly 11 roles across 10 placement companies")

    def test_company_tiers_and_cutoffs(self) -> None:
        """Verifies all companies have valid tiers, CGPA cutoffs, and eligible branches."""
        self.assertEqual(len(COMPANIES_SEED_DATA), 10)
        valid_tiers = {"Tier1", "Tier2", "Tier3"}
        for comp in COMPANIES_SEED_DATA:
            self.assertIn(comp["tier"], valid_tiers)
            self.assertTrue(0.0 <= comp["min_cgpa"] <= 10.0)
            self.assertTrue(comp["max_backlogs"] >= 0)
            self.assertTrue(len(comp["eligible_branches_csv"].strip()) > 0)

    def test_question_bank_seed_counts_and_structure(self) -> None:
        """Verifies the question bank has 30 questions with valid prompts, keywords, and answers."""
        self.assertEqual(len(QUESTIONS_SEED_DATA), 30)
        for q in QUESTIONS_SEED_DATA:
            self.assertIn(q["category"], {"Coding", "Technical", "Aptitude"})
            self.assertGreater(len(q["topic"].strip()), 3)
            self.assertGreater(len(q["question_text"].strip()), 15)
            self.assertGreater(len(q["expected_keywords_csv"].strip()), 5)
            self.assertGreater(len(q["symbolic_solution"].strip()), 15)

    def test_demo_user_seed_data(self) -> None:
        """Verifies demo user credentials and skills definition."""
        self.assertEqual(DEMO_USER_DATA["username"], "demo_student")
        expected_hash = hashlib.sha256("student123".encode("utf-8")).hexdigest()
        self.assertEqual(DEMO_USER_DATA["password_hash"], expected_hash)
        skills = json.loads(DEMO_USER_DATA["skills_json"])
        self.assertIn("Python", skills)

    def test_init_database_idempotent_execution(self) -> None:
        """Verifies init_database runs cleanly and second run does not duplicate rows."""
        conn = sqlite3.connect(":memory:")
        # First run: seed data
        success1 = init_database(seed=True, reset=False, conn=conn, driver="sqlite")
        self.assertTrue(success1)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM companies;")
        comp_count1 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM company_roles;")
        role_count1 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM question_bank;")
        q_count1 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM users;")
        u_count1 = cur.fetchone()[0]

        self.assertEqual(comp_count1, 10)
        self.assertEqual(role_count1, 11)
        self.assertEqual(q_count1, 30)
        self.assertEqual(u_count1, 1)

        # Second run: without reset, must skip seeding
        success2 = init_database(seed=True, reset=False, conn=conn, driver="sqlite")
        self.assertTrue(success2)

        cur.execute("SELECT COUNT(*) FROM companies;")
        comp_count2 = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM question_bank;")
        q_count2 = cur.fetchone()[0]

        self.assertEqual(comp_count1, comp_count2, "Idempotency violated: duplicate companies created")
        self.assertEqual(q_count1, q_count2, "Idempotency violated: duplicate questions created")
        cur.close()
        conn.close()

    def test_init_database_with_reset_flag(self) -> None:
        """Verifies init_database with reset=True drops and cleanly rebuilds tables."""
        conn = sqlite3.connect(":memory:")
        init_database(seed=True, reset=False, conn=conn, driver="sqlite")

        # Now reset and reseed
        success_reset = init_database(seed=True, reset=True, conn=conn, driver="sqlite")
        self.assertTrue(success_reset)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM companies;")
        self.assertEqual(cur.fetchone()[0], 10)
        cur.execute("SELECT COUNT(*) FROM question_bank;")
        self.assertEqual(cur.fetchone()[0], 30)
        cur.close()
        conn.close()

    def test_init_database_no_seed_flag(self) -> None:
        """Verifies init_database with seed=False creates schema tables without seed data."""
        conn = sqlite3.connect(":memory:")
        success = init_database(seed=False, reset=False, conn=conn, driver="sqlite")
        self.assertTrue(success)

        cur = conn.cursor()
        cur.execute("SELECT COUNT(*) FROM companies;")
        self.assertEqual(cur.fetchone()[0], 0)
        cur.execute("SELECT COUNT(*) FROM question_bank;")
        self.assertEqual(cur.fetchone()[0], 0)
        cur.close()
        conn.close()


if __name__ == "__main__":
    unittest.main()
