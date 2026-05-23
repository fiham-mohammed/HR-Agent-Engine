from typing import List, Dict, Any, Optional
from database.db import get_db_connection

def insert_audit_log(
    request_id: str,
    user_id: str,
    session_id: str,
    user_input: str,
    detected_intent: str,
    confidence_score: float,
    routed_agent: str,
    retrieved_memory_context: Optional[str],
    agent_response: str,
    execution_time_ms: float,
    status: str,
    errors: Optional[str] = None
) -> Dict[str, Any]:
    """Inserts a new log entry into the audit_logs table. Enforces SQLite append-only triggers."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO audit_logs (
                request_id, user_id, session_id, user_input, detected_intent,
                confidence_score, routed_agent, retrieved_memory_context,
                agent_response, execution_time_ms, status, errors
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id, user_id, session_id, user_input, detected_intent,
                confidence_score, routed_agent, retrieved_memory_context,
                agent_response, execution_time_ms, status, errors
            )
        )
        conn.commit()
        log_id = cursor.lastrowid
        
        # Retrieve the inserted row
        cursor.execute("SELECT * FROM audit_logs WHERE id = ?", (log_id,))
        row = cursor.fetchone()
        return dict(row)

def get_audit_logs(
    user_id: Optional[str] = None,
    limit: int = 50,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """Retrieves list of audit logs, optionally filtering by user_id."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        if user_id:
            cursor.execute(
                """
                SELECT * FROM audit_logs
                WHERE user_id = ?
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (user_id, limit, offset)
            )
        else:
            cursor.execute(
                """
                SELECT * FROM audit_logs
                ORDER BY timestamp DESC
                LIMIT ? OFFSET ?
                """,
                (limit, offset)
            )
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
