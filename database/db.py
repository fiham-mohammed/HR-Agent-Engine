import sqlite3
import os
from contextlib import contextmanager

# Read from environment variables — fallback to a safe relative path usable on any OS
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///hr_automation.db")


def get_db_path() -> str:
    """Parses and returns the absolute database path from the DATABASE_URL environment variable.

    Handles sqlite:/// (relative), sqlite:////absolute, and bare paths.
    Also handles the legacy Windows absolute path prefix /C:/... that some tools emit.
    """
    if DATABASE_URL.startswith("sqlite:///"):
        path = DATABASE_URL[len("sqlite:///"):]
    elif DATABASE_URL.startswith("sqlite://"):
        path = DATABASE_URL[len("sqlite://"):]
    else:
        path = DATABASE_URL

    # Handle legacy Windows absolute paths emitted as /C:/path -> C:/path
    if path.startswith("/") and len(path) > 2 and path[2] == ":":
        path = path.lstrip("/")

    return os.path.abspath(path)


@contextmanager
def get_db_connection():
    """Provides a thread-safe SQLite connection with row factory enabled.

    Bug fix: only calls os.makedirs when the resolved path actually has a
    parent directory component. Calling makedirs('') raises FileNotFoundError
    when the DB file lives in the current working directory.
    """
    db_path = get_db_path()
    parent_dir = os.path.dirname(db_path)
    if parent_dir:
        os.makedirs(parent_dir, exist_ok=True)

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        conn.execute("PRAGMA foreign_keys = ON;")
        yield conn
    finally:
        conn.close()


def init_db() -> None:
    """Initializes database tables and registers append-only triggers on audit_logs."""
    with get_db_connection() as conn:
        cursor = conn.cursor()

        # Create memories table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                session_id TEXT,
                content TEXT NOT NULL,
                memory_type TEXT NOT NULL CHECK(memory_type IN ('short_term', 'long_term')),
                significance_score INTEGER NOT NULL CHECK(significance_score BETWEEN 1 AND 10),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                metadata TEXT
            );
        """)

        # Create audit_logs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS audit_logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                request_id TEXT UNIQUE NOT NULL,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                user_id TEXT NOT NULL,
                session_id TEXT NOT NULL,
                user_input TEXT NOT NULL,
                detected_intent TEXT NOT NULL,
                confidence_score REAL NOT NULL,
                routed_agent TEXT NOT NULL,
                retrieved_memory_context TEXT,
                agent_response TEXT NOT NULL,
                execution_time_ms REAL NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('SUCCESS', 'FAILED')),
                errors TEXT
            );
        """)

        # Enforce append-only: block UPDATE
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS limit_audit_log_update
            BEFORE UPDATE ON audit_logs
            BEGIN
                SELECT RAISE(FAIL, 'Updates are not allowed on the append-only audit_logs table.');
            END;
        """)

        # Enforce append-only: block DELETE
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS limit_audit_log_delete
            BEFORE DELETE ON audit_logs
            BEGIN
                SELECT RAISE(FAIL, 'Deletions are not allowed on the append-only audit_logs table.');
            END;
        """)

        conn.commit()
