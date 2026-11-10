"""
Skillora Database Layer
Provides dual-driver database connectivity (MySQL with transparent SQLite fallback),
3NF relational schema DDL, unified Data Access Object (SkilloraDAO),
authentic Indian placement seed data, and idempotent initialization runner.
"""

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
    seed_companies,
    seed_database,
    seed_questions,
    seed_users,
)

__all__ = [
    "ConnectionManager",
    "UnifiedConnection",
    "UnifiedCursor",
    "get_db_connection",
    "get_driver_name",
    "reset_db_connection",
    "SkilloraDAO",
    "adapt_ddl_for_driver",
    "execute_ddl",
    "init_database",
    "COMPANIES_SEED_DATA",
    "QUESTIONS_SEED_DATA",
    "DEMO_USER_DATA",
    "seed_companies",
    "seed_questions",
    "seed_users",
    "seed_database",
]
