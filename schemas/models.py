from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

class RequestPayload(BaseModel):
    user_id: str = Field(..., description="Unique ID of the user requesting assistance")
    session_id: str = Field(..., description="Active session ID for conversation tracking")
    text: str = Field(..., description="Natural language request text")

class RequestResponse(BaseModel):
    request_id: str
    intent: str
    confidence: float
    response: str
    execution_time_ms: float
    status: str

class MemoryCreate(BaseModel):
    user_id: str
    session_id: Optional[str] = None
    content: str
    memory_type: str = Field("long_term", description="Must be 'short_term' or 'long_term'")
    significance_score: int = Field(..., ge=1, le=10, description="Significance rating from 1 to 10")

class MemoryResponse(BaseModel):
    id: int
    user_id: str
    session_id: Optional[str]
    content: str
    memory_type: str
    significance_score: int
    created_at: str
    metadata: Optional[Dict[str, Any]] = None

class AuditResponse(BaseModel):
    id: int
    request_id: str
    timestamp: str
    user_id: str
    session_id: str
    user_input: str
    detected_intent: str
    confidence_score: float
    routed_agent: str
    retrieved_memory_context: Optional[str]
    agent_response: str
    execution_time_ms: float
    status: str
    errors: Optional[str]

class HealthResponse(BaseModel):
    status: str
    database_connected: bool
    llm_provider: str
    timestamp: str
