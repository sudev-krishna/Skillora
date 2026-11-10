"""
Skillora Database Initialization Runner (server/db/init_db.py)
Provides idempotent schema creation and seed data bootstrapping.
Strictly offline, zero third-party dependencies (pure standard library).
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path
from typing import Any, Optional

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from server.db.dao import adapt_ddl_for_driver, execute_ddl
from server.db.seed_data import seed_database

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("skillora.db.init")


def _read_schema_sql() -> str:
    """Reads the DDL statements from server/db/schema.sql."""
    schema_path = Path(__file__).resolve().parent / "schema.sql"
    if not schema_path.exists():
        raise FileNotFoundError(f"Schema file not found at {schema_path}")
    return schema_path.read_text(encoding="utf-8")


def _drop_tables(conn: Any, driver: str) -> None:
    """Drops tables in reverse foreign-key dependency order."""
    drop_order = [
        "sympy_logs",
        "interview_sessions",
        "question_bank",
        "company_roles",
        "companies",
        "users"
    ]
    cursor = conn.cursor()
    if driver == "mysql":
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0;")
    for table in drop_order:
        cursor.execute(f"DROP TABLE IF EXISTS {table};")
    if driver == "mysql":
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1;")
    conn.commit()
    cursor.close()
    logger.info("Successfully dropped all existing tables in reverse dependency order.")


def _is_table_populated(conn: Any, table_name: str) -> bool:
    """Checks if a given table exists and contains records."""
    cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        row = cursor.fetchone()
        if row is None:
            return False
        if isinstance(row, dict):
            val = next(iter(row.values()))
            return val > 0
        return row[0] > 0
    except Exception:
        return False
    finally:
        cursor.close()


def init_database(
    seed: bool = True,
    reset: bool = False,
    conn: Optional[Any] = None,
    driver: Optional[str] = None
) -> bool:
    """
    Idempotent database creator and seed population entry point.

    Args:
        seed: If True, populates seed data when tables are empty or reset.
        reset: If True, drops all existing tables before recreating.
        conn: Optional existing DB connection. If None, acquires via connection manager.
        driver: Optional driver type ('sqlite' or 'mysql'). Auto-detected if conn is given.

    Returns:
        bool: True on success, False on error.
    """
    close_on_exit = False
    if conn is None:
        from server.db.connection import get_db_connection
        conn, driver = get_db_connection()
        close_on_exit = True
    elif driver is None:
        import sqlite3
        if hasattr(conn, "driver"):
            driver = getattr(conn, "driver")
        elif isinstance(conn, sqlite3.Connection):
            driver = "sqlite"
        else:
            driver = "mysql"

    driver_name = (driver or "sqlite").lower()

    try:
        # Enforce SQLite foreign keys
        if driver_name == "sqlite":
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_keys = ON;")
            cursor.close()

        # Handle reset
        if reset:
            logger.info("Reset requested: dropping existing database tables...")
            _drop_tables(conn, driver_name)

        # Execute schema DDL
        ddl = _read_schema_sql()
        execute_ddl(conn, driver_name, ddl)

        # Idempotent seeding check
        if seed:
            companies_populated = _is_table_populated(conn, "companies")
            questions_populated = _is_table_populated(conn, "question_bank")

            if companies_populated and questions_populated and not reset:
                logger.info("Database tables already populated with seed data. Skipping seeding.")
            else:
                logger.info("Populating database with Indian placement benchmarks and question bank...")
                stats = seed_database(conn, driver=driver_name)
                logger.info(
                    "Seed complete: %d companies, %d roles, %d questions, %d users.",
                    stats["companies"], stats["roles"], stats["questions"], stats["users"]
                )

        conn.commit()
        logger.info("Database initialization completed successfully.")
        return True

    except Exception as err:
        logger.error("Database initialization failed: %s", err, exc_info=True)
        try:
            conn.rollback()
        except Exception:
            pass
        return False

    finally:
        if close_on_exit and conn:
            try:
                conn.close()
            except Exception:
                pass


def main() -> int:
    """CLI runner entry point."""
    parser = argparse.ArgumentParser(
        description="Skillora Database Bootstrapping & Seed Migration Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--seed",
        action="store_true",
        default=True,
        help="Seed database with Tier 1/2/3 companies and 25+ questions (default: True)"
    )
    parser.add_argument(
        "--no-seed",
        action="store_false",
        dest="seed",
        help="Skip seeding after table creation"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        default=False,
        help="Drop existing tables and recreate cleanly before seeding"
    )

    args = parser.parse_args()
    success = init_database(seed=args.seed, reset=args.reset)
    return 0 if success else 1


if __name__ == "__main__":
    sys.exit(main())
