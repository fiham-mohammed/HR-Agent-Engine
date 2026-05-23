import json
import os
from typing import List, Dict, Any, Optional
from database.db import get_db_connection


def add_memory(
    user_id: str,
    content: str,
    memory_type: str,
    significance_score: int,
    session_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Adds a memory entry to the memories table and returns the inserted record."""
    metadata_json = json.dumps(metadata) if metadata else None

    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO memories (user_id, session_id, content, memory_type, significance_score, metadata)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (user_id, session_id, content, memory_type, significance_score, metadata_json)
        )
        conn.commit()
        memory_id = cursor.lastrowid
        cursor.execute("SELECT * FROM memories WHERE id = ?", (memory_id,))
        row = cursor.fetchone()
        res = dict(row)
        if res.get("metadata"):
            res["metadata"] = json.loads(res["metadata"])
        return res


def get_short_term_memories(session_id: str, limit: int = 5) -> List[Dict[str, Any]]:
    """Retrieves the most recent short-term memories for a session in chronological order.

    Bug fix: ORDER BY ASC directly in SQL rather than fetching DESC and reversing
    in Python — cleaner, fewer round-trips, and correct without the extra list reverse.
    """
    with get_db_connection() as conn:
        cursor = conn.cursor()
        # Sub-query grabs the latest N rows; outer query restores chronological order
        cursor.execute(
            """
            SELECT * FROM (
                SELECT * FROM memories
                WHERE session_id = ? AND memory_type = 'short_term'
                ORDER BY created_at DESC
                LIMIT ?
            ) ORDER BY created_at ASC
            """,
            (session_id, limit)
        )
        rows = cursor.fetchall()
        memories = []
        for row in rows:
            item = dict(row)
            if item.get("metadata"):
                item["metadata"] = json.loads(item["metadata"])
            memories.append(item)
        return memories


def get_long_term_memories(user_id: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Retrieves long-term memories for a user, ordered by most recent first."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT * FROM memories
            WHERE user_id = ? AND memory_type = 'long_term'
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (user_id, limit)
        )
        rows = cursor.fetchall()
        memories = []
        for row in rows:
            item = dict(row)
            if item.get("metadata"):
                item["metadata"] = json.loads(item["metadata"])
            memories.append(item)
        return memories


def get_memories(
    user_id: str,
    session_id: Optional[str] = None,
    memory_type: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Fetches memories filtering by user, optional session, and optional memory type."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        query = "SELECT * FROM memories WHERE user_id = ?"
        params: List[Any] = [user_id]

        if session_id:
            query += " AND session_id = ?"
            params.append(session_id)
        if memory_type:
            query += " AND memory_type = ?"
            params.append(memory_type)

        query += " ORDER BY created_at DESC"
        cursor.execute(query, params)
        rows = cursor.fetchall()

        memories = []
        for row in rows:
            item = dict(row)
            if item.get("metadata"):
                item["metadata"] = json.loads(item["metadata"])
            memories.append(item)
        return memories


def consolidate_to_ltm(
    user_id: str,
    session_id: str,
    content: str,
    significance_score: int,
    metadata: Optional[Dict[str, Any]] = None
) -> Optional[Dict[str, Any]]:
    """Promotes a fact to long-term memory if significance meets or exceeds the threshold.

    Threshold is read from LTM_SIGNIFICANCE_THRESHOLD env var (default 7).
    This is the single authoritative gate — callers should not duplicate this check.
    """
    threshold = int(os.getenv("LTM_SIGNIFICANCE_THRESHOLD", "7"))
    if significance_score >= threshold:
        return add_memory(
            user_id=user_id,
            content=content,
            memory_type="long_term",
            significance_score=significance_score,
            session_id=session_id,
            metadata=metadata
        )
    return None
