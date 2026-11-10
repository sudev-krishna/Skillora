"""
Skillora Data Access Object (server/db/dao.py)
Unified query layer providing dynamic parameter conversion (? vs %s),
thread-safe atomic transactions, and comprehensive CRUD methods.
Strictly zero third-party web frameworks (standard library + optional mysql-connector-python).
"""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

logger = logging.getLogger("skillora.db.dao")


# -----------------------------------------------------------------------------
# DDL Adaptation Utilities
# -----------------------------------------------------------------------------
def adapt_ddl_for_driver(ddl_sql: str, driver: str) -> str:
    """
    Translates canonical DDL to target engine dialect.

    Args:
        ddl_sql: The raw SQL text from schema.sql.
        driver: Either 'mysql' or 'sqlite'.

    Returns:
        Dialect-compliant DDL string.
    """
    driver_name = (driver or "sqlite").lower()
    if driver_name == "mysql":
        adapted = ddl_sql.replace("INTEGER PRIMARY KEY AUTOINCREMENT", "INT AUTO_INCREMENT PRIMARY KEY")
        adapted = adapted.replace("AUTOINCREMENT", "AUTO_INCREMENT")
        return adapted
    elif driver_name == "sqlite":
        adapted = ddl_sql.replace("INT AUTO_INCREMENT PRIMARY KEY", "INTEGER PRIMARY KEY AUTOINCREMENT")
        adapted = adapted.replace("AUTO_INCREMENT", "AUTOINCREMENT")
        return adapted
    return ddl_sql


def execute_ddl(conn: Any, driver: str, ddl_sql: str) -> None:
    """
    Executes multi-statement DDL against the active database connection.

    Args:
        conn: sqlite3.Connection or mysql.connector.connection.MySQLConnection or UnifiedConnection.
        driver: 'sqlite' or 'mysql'.
        ddl_sql: The raw or adapted DDL string.
    """
    adapted = adapt_ddl_for_driver(ddl_sql, driver)
    driver_name = (driver or "sqlite").lower()

    if driver_name == "sqlite":
        if hasattr(conn, "executescript"):
            conn.executescript(adapted)
        else:
            cur = conn.cursor()
            for statement in adapted.split(";"):
                stmt = statement.strip()
                if stmt:
                    cur.execute(stmt)
            conn.commit()
            cur.close()
    else:
        cur = conn.cursor()
        for statement in adapted.split(";"):
            stmt = statement.strip()
            if stmt:
                cur.execute(stmt)
        conn.commit()
        cur.close()


# -----------------------------------------------------------------------------
# SkilloraDAO Class
# -----------------------------------------------------------------------------
class SkilloraDAO:
    """
    Unified Data Access Object for Skillora.
    Abstracts SQLite 3.x and MySQL 8.x behind an identical Pythonic API.
    Provides thread safety via internal RLock and ensures transactional integrity.
    """

    def __init__(self, conn: Optional[Any] = None, driver: Optional[str] = None) -> None:
        """
        Initialize the DAO with an existing connection or load default fallback.

        Args:
            conn: Active database connection (sqlite3, mysql, or UnifiedConnection).
            driver: 'sqlite' or 'mysql'. Defaults to auto-detection if conn is given.
        """
        if conn is None or driver is None:
            from server.db.connection import get_db_connection
            self.conn, self.driver = get_db_connection()
            self.driver = self.driver.lower()
        else:
            self.conn = conn
            self.driver = driver.lower()

        self._lock = threading.RLock()

    # -------------------------------------------------------------------------
    # Internal Helpers
    # -------------------------------------------------------------------------
    def _format_query(self, query: str) -> str:
        """
        Dynamically adapts SQL query parameter placeholders to match the active driver.
        Canonical queries are written with '?' placeholders.
        """
        if self.driver == "mysql":
            return query.replace("?", "%s")
        elif self.driver == "sqlite":
            return query.replace("%s", "?")
        return query

    def _get_cursor(self) -> Any:
        """Returns a cursor configured for dictionary access."""
        if hasattr(self.conn, "cursor"):
            try:
                return self.conn.cursor(dictionary=True)
            except TypeError:
                return self.conn.cursor()
        raise RuntimeError("Active connection does not support cursor creation.")

    def _row_to_dict(self, cursor: Any, row: Any) -> Optional[Dict[str, Any]]:
        """Convert any cursor row format to a standard Python dictionary."""
        if row is None:
            return None
        if isinstance(row, dict):
            return dict(row)
        if hasattr(row, "keys"):
            return dict(row)
        if getattr(cursor, "description", None):
            columns = [col[0] for col in cursor.description]
            return dict(zip(columns, row))
        return dict(row)

    def _rows_to_dicts(self, cursor: Any, rows: List[Any]) -> List[Dict[str, Any]]:
        """Convert a sequence of cursor rows to a list of Python dictionaries."""
        return [self._row_to_dict(cursor, r) for r in rows if r is not None]  # type: ignore[misc]

    # -------------------------------------------------------------------------
    # Generic Query & Update Methods
    # -------------------------------------------------------------------------
    def execute_query(self, query: str, params: tuple = ()) -> List[Dict[str, Any]]:
        """Generic thread-safe read helper adapting query placeholders and mapping rows to dictionaries."""
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), params)
                rows = cur.fetchall()
                return self._rows_to_dicts(cur, rows)
            finally:
                cur.close()

    def execute_update(self, query: str, params: tuple = ()) -> int:
        """Generic thread-safe write helper managing transactions, commit, rollback."""
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), params)
                self.conn.commit()
                last_id = getattr(cur, "lastrowid", None)
                if last_id is not None and last_id > 0:
                    return last_id
                return getattr(cur, "rowcount", 0)
            except Exception as e:
                self.conn.rollback()
                logger.error(f"execute_update failed: {e}")
                raise
            finally:
                cur.close()

    def init_schema(self, ddl_path: Optional[str] = None) -> None:
        """Bootstraps database tables idempotently (CREATE TABLE IF NOT EXISTS)."""
        if ddl_path is None:
            ddl_path = os.path.join(os.path.dirname(__file__), "schema.sql")
        with open(ddl_path, "r", encoding="utf-8") as f:
            ddl_sql = f.read()
        with self._lock:
            execute_ddl(self.conn, self.driver, ddl_sql)

    # -------------------------------------------------------------------------
    # 1. User Authentication & Profile Methods
    # -------------------------------------------------------------------------
    def authenticate_user(self, username: str, password_hash: str) -> Optional[Dict[str, Any]]:
        """
        Verifies student credentials during AUTH_LOGIN.
        Returns user dictionary (without password_hash) or None.
        """
        query = (
            "SELECT user_id, username, full_name, branch, cgpa, backlogs, skills_json, created_at "
            "FROM users WHERE username = ? AND password_hash = ?"
        )
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), (username.strip(), password_hash))
                row = cur.fetchone()
                user_dict = self._row_to_dict(cur, row)
                if user_dict is None:
                    return None

                # Deserialize skills_json into Python list
                skills_raw = user_dict.get("skills_json")
                if skills_raw:
                    try:
                        user_dict["skills"] = json.loads(skills_raw)
                    except Exception:
                        user_dict["skills"] = []
                else:
                    user_dict["skills"] = []

                # Ensure password_hash is strictly omitted
                user_dict.pop("password_hash", None)
                return user_dict
            finally:
                cur.close()

    def register_user(
        self,
        username: str,
        password_hash: str,
        full_name: str,
        branch: str,
        cgpa: float,
        backlogs: int = 0,
        skills: Optional[List[str]] = None
    ) -> int:
        """
        Registers a new candidate during AUTH_REGISTER.
        Returns newly created user_id. Raises ValueError on duplicate or invalid data.
        """
        if not username or not isinstance(username, str) or not username.strip():
            raise ValueError("Username cannot be empty")
        if not password_hash or not isinstance(password_hash, str) or not password_hash.strip():
            raise ValueError("Password hash cannot be empty")
        if not isinstance(cgpa, (int, float)) or not (0.0 <= cgpa <= 10.0):
            raise ValueError("CGPA must be between 0.0 and 10.0")
        if not isinstance(backlogs, int) or backlogs < 0:
            raise ValueError("Backlogs must be a non-negative integer")

        skills_json_str = json.dumps(skills if skills is not None else [])
        query = (
            "INSERT INTO users (username, password_hash, full_name, branch, cgpa, backlogs, skills_json) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            username.strip(),
            password_hash,
            full_name.strip(),
            branch.strip(),
            float(cgpa),
            int(backlogs),
            skills_json_str
        )

        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), params)
                self.conn.commit()
                return cur.lastrowid
            except (sqlite3.IntegrityError, Exception) as exc:
                self.conn.rollback()
                err_msg = str(exc)
                if "UNIQUE" in err_msg.upper() or "DUPLICATE" in err_msg.upper() or "1062" in err_msg:
                    raise ValueError(f"Username already exists: {username}") from exc
                raise

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """Fetches student profile by user_id."""
        query = (
            "SELECT user_id, username, full_name, branch, cgpa, backlogs, skills_json, created_at "
            "FROM users WHERE user_id = ?"
        )
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), (int(user_id),))
                row = cur.fetchone()
                user_dict = self._row_to_dict(cur, row)
                if user_dict is None:
                    return None

                skills_raw = user_dict.get("skills_json")
                if skills_raw:
                    try:
                        user_dict["skills"] = json.loads(skills_raw)
                    except Exception:
                        user_dict["skills"] = []
                else:
                    user_dict["skills"] = []

                user_dict.pop("password_hash", None)
                return user_dict
            finally:
                cur.close()

    def update_user_profile(
        self,
        user_id: int,
        cgpa: Optional[float] = None,
        backlogs: Optional[int] = None,
        skills: Optional[List[str]] = None,
        branch: Optional[str] = None,
        full_name: Optional[str] = None
    ) -> bool:
        """Updates academic metrics or skills for the given user_id."""
        updates: List[str] = []
        params: List[Any] = []

        if cgpa is not None:
            updates.append("cgpa = ?")
            params.append(float(cgpa))
        if backlogs is not None:
            updates.append("backlogs = ?")
            params.append(int(backlogs))
        if skills is not None:
            updates.append("skills_json = ?")
            params.append(json.dumps(skills))
        if branch is not None:
            updates.append("branch = ?")
            params.append(branch.strip())
        if full_name is not None:
            updates.append("full_name = ?")
            params.append(full_name.strip())

        if not updates:
            return True

        params.append(int(user_id))
        query = f"UPDATE users SET {', '.join(updates)} WHERE user_id = ?"

        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), tuple(params))
                self.conn.commit()
                return cur.rowcount > 0
            except Exception as e:
                self.conn.rollback()
                logger.error(f"update_user_profile failed: {e}")
                raise
            finally:
                cur.close()

    # -------------------------------------------------------------------------
    # 2. Company & Role Benchmarking Methods
    # -------------------------------------------------------------------------
    def get_all_companies(self, tier_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Retrieves company benchmark catalog with eligible branches parsed."""
        if tier_filter:
            query = "SELECT * FROM companies WHERE tier = ? ORDER BY company_id ASC"
            params: tuple = (tier_filter.strip(),)
        else:
            query = "SELECT * FROM companies ORDER BY company_id ASC"
            params = ()

        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), params)
                rows = cur.fetchall()
                companies = self._rows_to_dicts(cur, rows)
                for comp in companies:
                    csv_branches = comp.get("eligible_branches_csv", "")
                    if csv_branches:
                        comp["eligible_branches"] = [b.strip() for b in csv_branches.split(",") if b.strip()]
                    else:
                        comp["eligible_branches"] = []
                return companies
            finally:
                cur.close()

    def get_company_by_id(self, company_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves single company metadata by company_id."""
        query = "SELECT * FROM companies WHERE company_id = ?"
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), (int(company_id),))
                row = cur.fetchone()
                comp = self._row_to_dict(cur, row)
                if comp is None:
                    return None
                csv_branches = comp.get("eligible_branches_csv", "")
                if csv_branches:
                    comp["eligible_branches"] = [b.strip() for b in csv_branches.split(",") if b.strip()]
                else:
                    comp["eligible_branches"] = []
                return comp
            finally:
                cur.close()

    def get_company_roles(self, company_id: int) -> List[Dict[str, Any]]:
        """Retrieves all recruitment roles associated with a company."""
        query = "SELECT * FROM company_roles WHERE company_id = ? ORDER BY package_lpa DESC"
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), (int(company_id),))
                rows = cur.fetchall()
                roles = self._rows_to_dicts(cur, rows)
                for role in roles:
                    round_raw = role.get("round_structure_json")
                    if round_raw:
                        try:
                            role["round_structure"] = json.loads(round_raw)
                        except Exception:
                            role["round_structure"] = {}
                    else:
                        role["round_structure"] = {}
                return roles
            finally:
                cur.close()

    def get_all_companies_with_roles(self, tier_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """High-efficiency loader returning companies with nested roles."""
        companies = self.get_all_companies(tier_filter=tier_filter)
        for comp in companies:
            comp["roles"] = self.get_company_roles(comp["company_id"])
        return companies

    # -------------------------------------------------------------------------
    # 3. Question Bank Repository Methods
    # -------------------------------------------------------------------------
    def get_questions_by_category(
        self,
        category: str,
        difficulty: Optional[str] = None,
        role_id: Optional[int] = None
    ) -> List[Dict[str, Any]]:
        """Supplies questions for interview simulation and mock tests."""
        where_clauses: List[str] = []
        params: List[Any] = []

        cat_upper = category.upper() if category else "ALL"
        if cat_upper in ("APTITUDE", "CODING", "TECHNICAL"):
            # Capitalize to match schema CHECK constraint ('Aptitude', 'Coding', 'Technical')
            normalized_cat = cat_upper.capitalize()
            where_clauses.append("category = ?")
            params.append(normalized_cat)

        if difficulty:
            where_clauses.append("difficulty = ?")
            params.append(difficulty.strip())

        if role_id is not None:
            where_clauses.append("(role_id = ? OR role_id IS NULL)")
            params.append(int(role_id))

        query = "SELECT * FROM question_bank"
        if where_clauses:
            query += " WHERE " + " AND ".join(where_clauses)
        query += " ORDER BY question_id ASC"

        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), tuple(params))
                rows = cur.fetchall()
                questions = self._rows_to_dicts(cur, rows)
                for q in questions:
                    kw_raw = q.get("expected_keywords_csv", "")
                    if kw_raw:
                        q["expected_keywords"] = [k.strip() for k in kw_raw.split(",") if k.strip()]
                    else:
                        q["expected_keywords"] = []

                    tc_raw = q.get("test_cases_json")
                    if tc_raw:
                        try:
                            q["test_cases"] = json.loads(tc_raw)
                        except Exception:
                            q["test_cases"] = {}
                    else:
                        q["test_cases"] = {}

                    # Model answer alias for symbolic_solution
                    q["model_answer"] = q.get("symbolic_solution", "")
                return questions
            finally:
                cur.close()

    def get_question_by_id(self, question_id: int) -> Optional[Dict[str, Any]]:
        """Fetches question by question_id."""
        query = "SELECT * FROM question_bank WHERE question_id = ?"
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), (int(question_id),))
                row = cur.fetchone()
                q = self._row_to_dict(cur, row)
                if q is None:
                    return None

                kw_raw = q.get("expected_keywords_csv", "")
                if kw_raw:
                    q["expected_keywords"] = [k.strip() for k in kw_raw.split(",") if k.strip()]
                else:
                    q["expected_keywords"] = []

                tc_raw = q.get("test_cases_json")
                if tc_raw:
                    try:
                        q["test_cases"] = json.loads(tc_raw)
                    except Exception:
                        q["test_cases"] = {}
                else:
                    q["test_cases"] = {}

                q["model_answer"] = q.get("symbolic_solution", "")
                return q
            finally:
                cur.close()

    # -------------------------------------------------------------------------
    # 4. Mock Interview Session Methods
    # -------------------------------------------------------------------------
    def save_interview_session(
        self,
        user_id: int,
        total_score: float = 0.0,
        feedback_json: Union[str, dict] = "",
        role_id: Optional[int] = None,
        aptitude_score: float = 0.0,
        coding_score: float = 0.0,
        technical_score: float = 0.0,
        composite_pri: Optional[float] = None
    ) -> int:
        """Records student mock interview performance and dimensional scores."""
        # Score normalization
        if composite_pri is None:
            composite_pri = float(total_score)
        if total_score == 0.0 and composite_pri > 0.0:
            total_score = composite_pri

        feedback_str = json.dumps(feedback_json) if isinstance(feedback_json, dict) else str(feedback_json)

        query = (
            "INSERT INTO interview_sessions ("
            "user_id, role_id, total_score, aptitude_score, coding_score, "
            "technical_score, composite_pri, feedback_json"
            ") VALUES (?, ?, ?, ?, ?, ?, ?, ?)"
        )
        params = (
            int(user_id),
            int(role_id) if role_id is not None else None,
            float(total_score),
            float(aptitude_score),
            float(coding_score),
            float(technical_score),
            float(composite_pri),
            feedback_str
        )

        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), params)
                self.conn.commit()
                return cur.lastrowid
            except Exception as e:
                self.conn.rollback()
                logger.error(f"save_interview_session failed: {e}")
                raise
            finally:
                cur.close()

    def get_user_interview_sessions(self, user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves interview history for Dashboard and Mock Interview review."""
        query = (
            "SELECT * FROM interview_sessions "
            "WHERE user_id = ? "
            "ORDER BY completed_at DESC, session_id DESC "
            "LIMIT ?"
        )
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), (int(user_id), int(limit)))
                rows = cur.fetchall()
                sessions = self._rows_to_dicts(cur, rows)
                for s in sessions:
                    fb_raw = s.get("feedback_json")
                    if fb_raw:
                        try:
                            s["feedback"] = json.loads(fb_raw)
                        except Exception:
                            s["feedback"] = fb_raw
                    else:
                        s["feedback"] = {}
                return sessions
            finally:
                cur.close()

    def get_interview_session_by_id(self, session_id: int) -> Optional[Dict[str, Any]]:
        """Retrieves single interview session details by session_id."""
        query = "SELECT * FROM interview_sessions WHERE session_id = ?"
        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), (int(session_id),))
                row = cur.fetchone()
                s = self._row_to_dict(cur, row)
                if s is None:
                    return None
                fb_raw = s.get("feedback_json")
                if fb_raw:
                    try:
                        s["feedback"] = json.loads(fb_raw)
                    except Exception:
                        s["feedback"] = fb_raw
                else:
                    s["feedback"] = {}
                return s
            finally:
                cur.close()

    # -------------------------------------------------------------------------
    # 5. SymPy & Math Profiling Log Methods
    # -------------------------------------------------------------------------
    def log_sympy_operation(
        self,
        user_id: Optional[int],
        expression: str,
        result: str,
        operation_type: str = "RECURRENCE",
        derived_big_o: Optional[str] = None,
        empirical_runtime_ms: Optional[float] = None
    ) -> int:
        """Records symbolic algebra derivation or code sandbox execution."""
        query = (
            "INSERT INTO sympy_logs ("
            "user_id, operation_type, expression, result, derived_big_o, empirical_runtime_ms"
            ") VALUES (?, ?, ?, ?, ?, ?)"
        )
        params = (
            int(user_id) if user_id is not None else None,
            operation_type.strip(),
            expression.strip(),
            result.strip(),
            derived_big_o.strip() if derived_big_o else None,
            float(empirical_runtime_ms) if empirical_runtime_ms is not None else None
        )

        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), params)
                self.conn.commit()
                return cur.lastrowid
            except Exception as e:
                self.conn.rollback()
                logger.error(f"log_sympy_operation failed: {e}")
                raise
            finally:
                cur.close()

    def get_sympy_logs(self, user_id: Optional[int] = None, limit: int = 50) -> List[Dict[str, Any]]:
        """Retrieves mathematical derivation history."""
        if user_id is not None:
            query = (
                "SELECT * FROM sympy_logs "
                "WHERE user_id = ? "
                "ORDER BY timestamp DESC, log_id DESC "
                "LIMIT ?"
            )
            params: tuple = (int(user_id), int(limit))
        else:
            query = "SELECT * FROM sympy_logs ORDER BY timestamp DESC, log_id DESC LIMIT ?"
            params = (int(limit),)

        with self._lock:
            cur = self._get_cursor()
            try:
                cur.execute(self._format_query(query), params)
                rows = cur.fetchall()
                logs = self._rows_to_dicts(cur, rows)
                for log in logs:
                    log["recurrence_input"] = log.get("expression", "")
                    log["solved_closed_form"] = log.get("result", "")
                return logs
            finally:
                cur.close()

    # -------------------------------------------------------------------------
    # 6. Dashboard Aggregated Metrics Method
    # -------------------------------------------------------------------------
    def get_dashboard_stats(self, user_id: int) -> Dict[str, Any]:
        """Generates consolidated statistics for GET_DASHBOARD_STATS."""
        sessions = self.get_user_interview_sessions(user_id, limit=5)
        all_sessions = self.get_user_interview_sessions(user_id, limit=1000)
        sympy_logs = self.get_sympy_logs(user_id, limit=1000)

        recent_pri = float(sessions[0]["composite_pri"]) if sessions else 0.0

        if recent_pri >= 85.0:
            top_tier = "Tier 1 (Product Companies)"
        elif recent_pri >= 70.0:
            top_tier = "Tier 2 (Technology Specialists)"
        elif recent_pri >= 50.0:
            top_tier = "Tier 3 (IT Services)"
        else:
            top_tier = "Needs Preparation"

        return {
            "user_id": user_id,
            "recent_pri": recent_pri,
            "sessions_count": len(all_sessions),
            "recurrence_count": len(sympy_logs),
            "top_eligible_tier": top_tier,
            "recent_sessions": sessions
        }
