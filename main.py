import asyncio
import uuid
import os
from datetime import datetime, timezone
from typing import List, Optional
from fastapi import FastAPI, HTTPException, status, Query, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

# Load env variables before importing local packages
load_dotenv()

from schemas.models import RequestPayload, RequestResponse, MemoryCreate, MemoryResponse, AuditResponse, HealthResponse
from agents.orchestrator import run_orchestrator
from database.memory_store import get_memories, add_memory
from database.audit_logger import get_audit_logs
from database.db import get_db_connection
from utils.logger import get_logger

logger = get_logger("main")

app = FastAPI(
    title="ZeloraTech HR Automation Multi-Agent Engine",
    description="Orchestrator Agent routing HR queries using Langgraph, SQLite, and Two-tier Memory.",
    version="1.0.0"
)

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Error Handlers (Polite responses, no raw Python traces) ---

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Intercepts unhandled server exceptions and returns a polite generic message."""
    logger.error(f"Unhandled system error on path {request.url.path}: {exc}", exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "We experienced an unexpected issue on our server. Please try your request again shortly."}
    )

@app.exception_handler(HTTPException)
async def custom_http_exception_handler(request: Request, exc: HTTPException):
    """Intercepts custom HTTP exceptions to keep output format clean."""
    logger.warning(f"HTTPException on {request.url.path}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail}
    )

# --- Endpoints ---

@app.get("/")
async def root():
    """Friendly homepage so the base URL does not return 404."""
    return {
        "message": "ZeloraTech HR Engine is running",
        "docs": "/docs",
        "health": "/api/v1/health"
    }


# 1. Request Handling Endpoint
@app.post("/api/v1/request", response_model=RequestResponse, status_code=status.HTTP_200_OK)
async def orchestrate_request(payload: RequestPayload):
    """Routes natural language request to appropriate specialist sub-agent with memory context."""
    logger.info(f"Received request from user {payload.user_id} in session {payload.session_id}")
    
    try:
        # Run the orchestrator graph with a 10.0-second timeout limit
        result = await asyncio.wait_for(
            asyncio.to_thread(run_orchestrator, payload.user_id, payload.session_id, payload.text),
            timeout=60.0
        )
        return result
    except asyncio.TimeoutError:
        logger.error(f"Orchestration timed out for user {payload.user_id}")
        return RequestResponse(
            request_id=f"req_timeout_{uuid.uuid4().hex[:6]}",
            intent="Clarification",
            confidence=0.0,
            response="I'm sorry, but your request took longer than expected to process. Please try asking again in simpler terms.",
            execution_time_ms=10000.0,
            status="FAILED"
        )
    except Exception as e:
        logger.error(f"Orchestration failed for user {payload.user_id}: {e}", exc_info=True)
        return RequestResponse(
            request_id=f"req_err_{uuid.uuid4().hex[:6]}",
            intent="Clarification",
            confidence=0.0,
            response="I'm sorry, but I was unable to complete your request due to an internal processing error.",
            execution_time_ms=0.0,
            status="FAILED"
        )

# 2. Audit Retrieval Endpoint
@app.get("/api/v1/audit", response_model=List[AuditResponse])
async def get_audits(
    user_id: Optional[str] = Query(None, description="Filter audit logs by specific user ID"),
    limit: int = Query(50, ge=1, le=100, description="Max number of logs to return"),
    offset: int = Query(0, ge=0, description="Offset for pagination")
):
    """Retrieves records from the append-only audit trail."""
    try:
        logs = get_audit_logs(user_id=user_id, limit=limit, offset=offset)
        # Parse SQL rows into AuditResponse format
        parsed_logs = []
        for log in logs:
            parsed_logs.append(AuditResponse(
                id=log["id"],
                request_id=log["request_id"],
                timestamp=str(log["timestamp"]),
                user_id=log["user_id"],
                session_id=log["session_id"],
                user_input=log["user_input"],
                detected_intent=log["detected_intent"],
                confidence_score=log["confidence_score"],
                routed_agent=log["routed_agent"],
                retrieved_memory_context=log["retrieved_memory_context"],
                agent_response=log["agent_response"],
                execution_time_ms=log["execution_time_ms"],
                status=log["status"],
                errors=log["errors"]
            ))
        return parsed_logs
    except Exception as e:
        logger.error(f"Failed to fetch audit logs: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve audit records due to a database issue."
        )

# 3. Memory Retrieval Endpoint
@app.get("/api/v1/memory", response_model=List[MemoryResponse])
async def get_user_memories(
    user_id: str = Query(..., description="Unique ID of the user"),
    session_id: Optional[str] = Query(None, description="Filter by active session"),
    type: Optional[str] = Query(None, description="Filter by memory type: 'short_term' or 'long_term'")
):
    """Fetches user memories (both short-term sliding conversations and consolidated long-term rules)."""
    if type and type not in ("short_term", "long_term"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory type filter must be either 'short_term' or 'long_term'."
        )
        
    try:
        memories = get_memories(user_id=user_id, session_id=session_id, memory_type=type)
        response_data = []
        for m in memories:
            response_data.append(MemoryResponse(
                id=m["id"],
                user_id=m["user_id"],
                session_id=m["session_id"],
                content=m["content"],
                memory_type=m["memory_type"],
                significance_score=m["significance_score"],
                created_at=str(m["created_at"]),
                metadata=m.get("metadata")
            ))
        return response_data
    except Exception as e:
        logger.error(f"Failed to fetch memories: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not retrieve user memory records."
        )

# 4. Memory Creation Endpoint
@app.post("/api/v1/memory", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_user_memory(payload: MemoryCreate):
    """Manually inserts or updates a memory record for a user."""
    if payload.memory_type not in ("short_term", "long_term"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Memory type must be 'short_term' or 'long_term'."
        )
        
    try:
        memory = add_memory(
            user_id=payload.user_id,
            content=payload.content,
            memory_type=payload.memory_type,
            significance_score=payload.significance_score,
            session_id=payload.session_id,
            metadata={"manually_added": True}
        )
        return MemoryResponse(
            id=memory["id"],
            user_id=memory["user_id"],
            session_id=memory["session_id"],
            content=memory["content"],
            memory_type=memory["memory_type"],
            significance_score=memory["significance_score"],
            created_at=str(memory["created_at"]),
            metadata=memory.get("metadata")
        )
    except Exception as e:
        logger.error(f"Failed to create memory: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Could not insert new memory record."
        )

# 5. Health Monitoring Endpoint
@app.get("/api/v1/health", response_model=HealthResponse)
async def check_health():
    """Monitors application system health, database connections, and active LLM configuration."""
    db_connected = False
    try:
        with get_db_connection() as conn:
            conn.execute("SELECT 1;")
            db_connected = True
    except Exception as e:
        logger.error(f"Health check database connection failed: {e}")
        
    llm_provider = os.getenv("LLM_PROVIDER", "mock")
    system_status = "healthy" if db_connected else "unhealthy"
    
    return HealthResponse(
        status=system_status,
        database_connected=db_connected,
        llm_provider=llm_provider,
        timestamp=datetime.now(timezone.utc).isoformat()
    )
