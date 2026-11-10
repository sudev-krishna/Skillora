"""
Skillora Dual-Driver Database Connection Manager (server/db/connection.py)
Provides MySQL connection with transparent fallback to local SQLite (skillora_offline.db),
foreign key enforcement, thread-local connection safety, and unified connection wrapping.
Strictly zero third-party web frameworks (pure standard library + optional mysql-connector-python).
"""

from __future__ import annotations

import logging
import os
import socket
import sqlite3
import threading
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Union

logger = logging.getLogger("skillora.db.connection")

# Optional MySQL Connector import
try:
    import mysql.connector
    from mysql.connector import Error as MySQLError
    from mysql.connector.connection import MySQLConnection
    from mysql.connector.pooling import MySQLConnectionPool
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    MySQLError = Exception
    MySQLConnection = Any
    MySQLConnectionPool = Any
    logger.info("mysql-connector-python not installed. Operating in pure SQLite mode.")

# -----------------------------------------------------------------------------
# Configuration & Constants
# -----------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_SQLITE_FILENAME = "skillora_offline.db"
DEFAULT_SQLITE_PATH = str(PROJECT_ROOT / DEFAULT_SQLITE_FILENAME)

DEFAULT_MYSQL_HOST = os.environ.get("SKILLORA_MYSQL_HOST", "localhost")
DEFAULT_MYSQL_PORT = int(os.environ.get("SKILLORA_MYSQL_PORT", "3306"))
DEFAULT_MYSQL_USER = os.environ.get("SKILLORA_MYSQL_USER", "root")
DEFAULT_MYSQL_PASSWORD = os.environ.get("SKILLORA_MYSQL_PASSWORD", "")
DEFAULT_MYSQL_DATABASE = os.environ.get("SKILLORA_MYSQL_DATABASE", "skillora")
DEFAULT_TIMEOUT_SEC = float(os.environ.get("SKILLORA_DB_TIMEOUT", "2.0"))


# -----------------------------------------------------------------------------
# Unified Cursor Wrapper
# -----------------------------------------------------------------------------
class UnifiedCursor:
    """Cursor wrapper standardizing dictionary access and placeholder adaptation."""

    def __init__(self, raw_cursor: Any, driver: str, as_dict: bool = True) -> None:
        self.raw_cursor = raw_cursor
        self.driver = driver
        self.as_dict = as_dict

    def execute(self, sql: str, params: Optional[Union[tuple, list, dict]] = None) -> Any:
        if params is None:
            return self.raw_cursor.execute(sql)
        return self.raw_cursor.execute(sql, params)

    def executemany(self, sql: str, seq_of_params: Any) -> Any:
        return self.raw_cursor.executemany(sql, seq_of_params)

    def fetchone(self) -> Optional[Union[Dict[str, Any], Tuple[Any, ...]]]:
        row = self.raw_cursor.fetchone()
        if row is None:
            return None
        if self.as_dict:
            if isinstance(row, dict):
                return row
            if hasattr(row, "keys"):  # sqlite3.Row
                return dict(row)
            if getattr(self.raw_cursor, "description", None):
                columns = [col[0] for col in self.raw_cursor.description]
                return dict(zip(columns, row))
        return row

    def fetchall(self) -> List[Any]:
        rows = self.raw_cursor.fetchall()
        if not rows:
            return []
        if self.as_dict:
            res: List[Dict[str, Any]] = []
            for row in rows:
                if isinstance(row, dict):
                    res.append(row)
                elif hasattr(row, "keys"):
                    res.append(dict(row))
                elif getattr(self.raw_cursor, "description", None):
                    columns = [col[0] for col in self.raw_cursor.description]
                    res.append(dict(zip(columns, row)))
                else:
                    res.append(row)
            return res
        return rows

    def fetchmany(self, size: Optional[int] = None) -> List[Any]:
        rows = self.raw_cursor.fetchmany(size) if size is not None else self.raw_cursor.fetchmany()
        if not rows:
            return []
        if self.as_dict:
            res: List[Dict[str, Any]] = []
            for row in rows:
                if isinstance(row, dict):
                    res.append(row)
                elif hasattr(row, "keys"):
                    res.append(dict(row))
                elif getattr(self.raw_cursor, "description", None):
                    columns = [col[0] for col in self.raw_cursor.description]
                    res.append(dict(zip(columns, row)))
                else:
                    res.append(row)
            return res
        return rows

    @property
    def lastrowid(self) -> Optional[int]:
        return getattr(self.raw_cursor, "lastrowid", None)

    @property
    def rowcount(self) -> int:
        return getattr(self.raw_cursor, "rowcount", -1)

    @property
    def description(self) -> Any:
        return getattr(self.raw_cursor, "description", None)

    def close(self) -> None:
        try:
            self.raw_cursor.close()
        except Exception:
            pass

    def __iter__(self) -> Iterator[Any]:
        return iter(self.fetchall())

    def __enter__(self) -> UnifiedCursor:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw_cursor, name)


# -----------------------------------------------------------------------------
# Unified Connection Wrapper
# -----------------------------------------------------------------------------
class UnifiedConnection:
    """
    Unified connection object bridging MySQL and SQLite connections.
    Supports:
      1. Direct method calls (cursor, commit, rollback, close, execute, executemany, executescript)
      2. 2-tuple unpacking: conn, driver = get_db_connection()
      3. Indexing: conn_tuple[0] -> conn, conn_tuple[1] -> driver
      4. Context manager (commits on success, rolls back on exception)
      5. Attribute delegation to raw DB-API connection object
    """

    def __init__(
        self,
        raw_connection: Any,
        driver: str,
        write_lock: Optional[threading.RLock] = None
    ) -> None:
        self.raw_connection = raw_connection
        self.driver = driver
        self._write_lock = write_lock or threading.RLock()

    def cursor(self, dictionary: bool = True, **kwargs: Any) -> UnifiedCursor:
        if self.driver == "mysql":
            raw_cur = self.raw_connection.cursor(dictionary=dictionary, **kwargs)
            return UnifiedCursor(raw_cur, driver="mysql", as_dict=dictionary)
        else:
            # SQLite: enable row_factory for dictionary access
            if dictionary:
                self.raw_connection.row_factory = sqlite3.Row
            raw_cur = self.raw_connection.cursor(**kwargs)
            return UnifiedCursor(raw_cur, driver="sqlite", as_dict=dictionary)

    def commit(self) -> None:
        self.raw_connection.commit()

    def rollback(self) -> None:
        self.raw_connection.rollback()

    def close(self) -> None:
        try:
            self.raw_connection.close()
        except Exception:
            pass

    def execute(self, sql: str, params: Optional[Union[tuple, list, dict]] = None) -> UnifiedCursor:
        cur = self.cursor(dictionary=True)
        cur.execute(sql, params)
        return cur

    def executemany(self, sql: str, seq_of_params: Any) -> UnifiedCursor:
        cur = self.cursor(dictionary=True)
        cur.executemany(sql, seq_of_params)
        return cur

    def executescript(self, sql_script: str) -> None:
        if self.driver == "sqlite":
            if hasattr(self.raw_connection, "executescript"):
                self.raw_connection.executescript(sql_script)
            else:
                cur = self.raw_connection.cursor()
                for stmt in sql_script.split(";"):
                    s = stmt.strip()
                    if s:
                        cur.execute(s)
                self.raw_connection.commit()
                cur.close()
        else:
            cur = self.raw_connection.cursor()
            for stmt in sql_script.split(";"):
                s = stmt.strip()
                if s:
                    cur.execute(s)
            self.raw_connection.commit()
            cur.close()

    def __enter__(self) -> UnifiedConnection:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        if exc_type is not None:
            self.rollback()
        else:
            self.commit()

    def __iter__(self) -> Iterator[Union[UnifiedConnection, str]]:
        yield self
        yield self.driver

    def __getitem__(self, index: int) -> Union[UnifiedConnection, str]:
        if index == 0:
            return self
        elif index == 1:
            return self.driver
        raise IndexError(f"Index {index} out of range for UnifiedConnection")

    def __len__(self) -> int:
        return 2

    def __getattr__(self, name: str) -> Any:
        return getattr(self.raw_connection, name)


# -----------------------------------------------------------------------------
# Database Connection Manager (Singleton / Pool)
# -----------------------------------------------------------------------------
class ConnectionManager:
    """
    Manages dual-driver database connection acquisition, probe/caching,
    thread-local storage, and pooling.
    """

    _instance: Optional[ConnectionManager] = None
    _init_lock = threading.Lock()

    def __new__(cls) -> ConnectionManager:
        with cls._init_lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self) -> None:
        if getattr(self, "_initialized", False):
            return
        self._lock = threading.Lock()
        self._write_lock = threading.RLock()
        self._thread_local = threading.local()
        self._active_driver: Optional[str] = None
        self._mysql_pool: Optional[Any] = None
        self._configured_sqlite_path = os.environ.get("SKILLORA_DB_PATH", DEFAULT_SQLITE_PATH)
        self._driver_override = os.environ.get("SKILLORA_DB_DRIVER", "").lower().strip() or None
        self._initialized = True

    def reset(self) -> None:
        """Reset driver determination and active connections (for testing)."""
        with self._lock:
            self._active_driver = None
            self._mysql_pool = None
            self._driver_override = os.environ.get("SKILLORA_DB_DRIVER", "").lower().strip() or None
            self._configured_sqlite_path = os.environ.get("SKILLORA_DB_PATH", DEFAULT_SQLITE_PATH)
            # Close existing thread-local connections if any
            for attr in list(vars(self._thread_local).keys()):
                conn = getattr(self._thread_local, attr, None)
                if conn is not None and hasattr(conn, "close"):
                    try:
                        conn.close()
                    except Exception:
                        pass
            self._thread_local = threading.local()

    def determine_driver(self, database: Optional[str] = DEFAULT_MYSQL_DATABASE) -> str:
        """Probe MySQL with timeout or return cached/overridden driver."""
        with self._lock:
            override = os.environ.get("SKILLORA_DB_DRIVER", "").lower().strip() or self._driver_override
            if override in ("mysql", "sqlite"):
                return override
            if self._active_driver is not None:
                return self._active_driver

            if not MYSQL_AVAILABLE:
                logger.info("MySQL connector not available. Using SQLite driver.")
                self._active_driver = "sqlite"
                return "sqlite"

            # Fast TCP probe to avoid multi-second OS connect timeouts if MySQL daemon is not running
            mysql_probe_host = "127.0.0.1" if DEFAULT_MYSQL_HOST in ("localhost", "127.0.0.1") else DEFAULT_MYSQL_HOST
            try:
                probe_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                probe_sock.settimeout(0.2)
                probe_sock.connect((mysql_probe_host, DEFAULT_MYSQL_PORT))
                probe_sock.close()
            except Exception as probe_exc:
                target_sqlite = os.environ.get("SKILLORA_DB_PATH", self._configured_sqlite_path)
                logger.info(
                    f"MySQL service not active on {mysql_probe_host}:{DEFAULT_MYSQL_PORT} ({probe_exc}). "
                    f"Using local SQLite database: {target_sqlite}"
                )
                self._active_driver = "sqlite"
                return "sqlite"

            # Probe MySQL with strict timeout
            logger.info(
                f"Attempting primary MySQL connection to {DEFAULT_MYSQL_HOST}:{DEFAULT_MYSQL_PORT} "
                f"(database='{database}', timeout={DEFAULT_TIMEOUT_SEC}s)..."
            )
            try:
                test_conn = mysql.connector.connect(
                    host=DEFAULT_MYSQL_HOST,
                    port=DEFAULT_MYSQL_PORT,
                    user=DEFAULT_MYSQL_USER,
                    password=DEFAULT_MYSQL_PASSWORD,
                    database=database,
                    connection_timeout=int(DEFAULT_TIMEOUT_SEC),
                )
                if test_conn.is_connected():
                    test_conn.close()
                    logger.info("Successfully connected to MySQL database.")
                    self._active_driver = "mysql"
                    return "mysql"
            except (MySQLError, Exception) as exc:
                target_sqlite = os.environ.get("SKILLORA_DB_PATH", self._configured_sqlite_path)
                logger.warning(
                    f"MySQL connection to {DEFAULT_MYSQL_HOST}:{DEFAULT_MYSQL_PORT} failed ({exc}). "
                    f"Transparently falling back to local SQLite database: {target_sqlite}"
                )

            self._active_driver = "sqlite"
            return "sqlite"

    def _create_sqlite_connection(self, path: str) -> sqlite3.Connection:
        """Open a SQLite connection and configure PRAGMA settings."""
        if path != ":memory:" and not path.startswith("file:"):
            parent_dir = os.path.dirname(os.path.abspath(path))
            if parent_dir and not os.path.exists(parent_dir):
                os.makedirs(parent_dir, exist_ok=True)

        conn = sqlite3.connect(
            path,
            timeout=30.0,
            check_same_thread=False
        )
        conn.row_factory = sqlite3.Row

        # Mandatory Pragmas
        conn.execute("PRAGMA foreign_keys = ON;")
        if path != ":memory:" and not path.startswith("file:"):
            try:
                conn.execute("PRAGMA journal_mode = WAL;")
            except Exception:
                pass
        conn.execute("PRAGMA busy_timeout = 30000;")

        return conn

    def _get_mysql_connection(self, database: Optional[str]) -> Any:
        """Acquire connection from MySQL pool or direct connection."""
        db_name = database or DEFAULT_MYSQL_DATABASE
        with self._lock:
            if self._mysql_pool is None:
                try:
                    self._mysql_pool = MySQLConnectionPool(
                        pool_name="skillora_pool",
                        pool_size=5,
                        host=DEFAULT_MYSQL_HOST,
                        port=DEFAULT_MYSQL_PORT,
                        user=DEFAULT_MYSQL_USER,
                        password=DEFAULT_MYSQL_PASSWORD,
                        database=db_name,
                        connection_timeout=int(DEFAULT_TIMEOUT_SEC),
                    )
                except Exception:
                    return mysql.connector.connect(
                        host=DEFAULT_MYSQL_HOST,
                        port=DEFAULT_MYSQL_PORT,
                        user=DEFAULT_MYSQL_USER,
                        password=DEFAULT_MYSQL_PASSWORD,
                        database=db_name,
                        connection_timeout=int(DEFAULT_TIMEOUT_SEC),
                    )
        return self._mysql_pool.get_connection()

    def get_connection(
        self,
        database: Optional[str] = DEFAULT_MYSQL_DATABASE,
        sqlite_path: Optional[str] = None,
        driver: Optional[str] = None,
        thread_local: bool = True
    ) -> UnifiedConnection:
        """
        Acquire a UnifiedConnection.
        If thread_local is True, returns/caches a connection for the calling thread.
        """
        active_driver = driver or self.determine_driver(database=database)
        target_sqlite_path = sqlite_path or os.environ.get("SKILLORA_DB_PATH", self._configured_sqlite_path)

        if active_driver == "mysql":
            raw_conn = self._get_mysql_connection(database)
            return UnifiedConnection(raw_conn, driver="mysql", write_lock=self._write_lock)

        # SQLite path
        if not thread_local or target_sqlite_path == ":memory:":
            raw_conn = self._create_sqlite_connection(target_sqlite_path)
            return UnifiedConnection(raw_conn, driver="sqlite", write_lock=self._write_lock)

        # Thread-local SQLite connection
        conn_attr = f"_sqlite_conn_{target_sqlite_path}"
        existing_conn = getattr(self._thread_local, conn_attr, None)
        if existing_conn is not None:
            try:
                existing_conn.execute("SELECT 1;")
                return UnifiedConnection(existing_conn, driver="sqlite", write_lock=self._write_lock)
            except Exception:
                existing_conn = None

        new_conn = self._create_sqlite_connection(target_sqlite_path)
        setattr(self._thread_local, conn_attr, new_conn)
        return UnifiedConnection(new_conn, driver="sqlite", write_lock=self._write_lock)


# -----------------------------------------------------------------------------
# Module Interface Functions
# -----------------------------------------------------------------------------
_manager = ConnectionManager()


def get_db_connection(
    database: Optional[str] = DEFAULT_MYSQL_DATABASE,
    sqlite_path: Optional[str] = None,
    driver: Optional[str] = None,
    thread_local: bool = True
) -> Tuple[UnifiedConnection, str]:
    """
    Authoritative connection entry point.
    Returns:
        UnifiedConnection instance which unpacks as (conn, driver).
    """
    unified_conn = _manager.get_connection(
        database=database,
        sqlite_path=sqlite_path,
        driver=driver,
        thread_local=thread_local
    )
    return unified_conn  # type: ignore[return-value]


def get_driver_name() -> str:
    """Return active driver name ('mysql' or 'sqlite')."""
    return _manager.determine_driver()


def reset_db_connection() -> None:
    """Reset driver determination and active connection pool (for test isolation)."""
    _manager.reset()
