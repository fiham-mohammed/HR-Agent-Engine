import time
import uuid
from typing import Dict, Any, List, TypedDict, Tuple, Optional
from langgraph.graph import StateGraph, START, END

from utils.llm import LLMProvider
from utils.logger import get_logger
from agents.router import IntentRouter
from agents.scheduling import SchedulingAgent
from agents.leave import LeaveAgent
from agents.compliance import ComplianceAgent
from agents.clarification import ClarificationAgent
from database.memory_store import get_short_term_memories, get_long_term_memories, add_memory, consolidate_to_ltm
from database.audit_logger import insert_audit_log

logger = get_logger("orchestrator")


class AgentState(TypedDict):
    request_id: str
    user_id: str
    session_id: str
    user_input: str
    detected_intent: str
    confidence_score: float
    memory_context: str
    agent_response: str
    retry_count: int
    start_time: float
    errors: List[str]


# Initialize LLM Provider and Specialist Agents
llm_provider = LLMProvider()
router_agent = IntentRouter(llm_provider)
scheduling_agent = SchedulingAgent(llm_provider)
leave_agent = LeaveAgent(llm_provider)
compliance_agent = ComplianceAgent(llm_provider)
clarification_agent = ClarificationAgent(llm_provider)


def execute_with_retry(func, *args, max_retries: int = 3, initial_delay: float = 1.0, **kwargs):
    """Executes a function with exponential backoff retry logic.

    Bug fix: the sleep now only occurs between attempts, not after the final
    failed attempt, avoiding unnecessary latency before re-raising.
    """
    delay = initial_delay
    for attempt in range(max_retries):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            if attempt == max_retries - 1:
                # Final attempt — raise immediately without sleeping
                raise e
            logger.warning(f"Attempt {attempt + 1} failed: {e}. Retrying in {delay}s...")
            time.sleep(delay)
            delay *= 2


# 1. Retrieve Memory Node
def retrieve_memory_node(state: AgentState) -> Dict[str, Any]:
    """Fetches STM (session) and LTM (user) memories and injects them as context."""
    logger.info(f"[{state['request_id']}] Retrieving memory for user {state['user_id']}, session {state['session_id']}")
    try:
        stm = execute_with_retry(get_short_term_memories, state['session_id'], limit=5)
        ltm = execute_with_retry(get_long_term_memories, state['user_id'], limit=5)

        context_parts = []
        if stm:
            context_parts.append("Recent Conversation History (Short-Term Memory):")
            for m in stm:
                context_parts.append(f"- {m['content']}")
        if ltm:
            context_parts.append("User Background Facts (Long-Term Memory):")
            for m in ltm:
                context_parts.append(f"- {m['content']}")

        memory_context = "\n".join(context_parts) if context_parts else "No previous history."
        return {"memory_context": memory_context}
    except Exception as e:
        logger.error(f"Failed to retrieve memory: {e}")
        return {"memory_context": "No previous history due to retrieval error.", "errors": state.get("errors", []) + [str(e)]}


# 2. Router Node
def router_node(state: AgentState) -> Dict[str, Any]:
    """Classifies user intent and returns detected_intent + confidence_score."""
    logger.info(f"[{state['request_id']}] Classifying intent for input: '{state['user_input']}'")
    try:
        intent, confidence = execute_with_retry(router_agent.route_query, state['user_input'])
        logger.info(f"[{state['request_id']}] Router result: Intent={intent}, Confidence={confidence}")
        return {"detected_intent": intent, "confidence_score": confidence}
    except Exception as e:
        logger.error(f"Router failed: {e}")
        return {"detected_intent": "Clarification", "confidence_score": 0.0, "errors": state.get("errors", []) + [str(e)]}


# Conditional Routing Logic
def route_decision(state: AgentState) -> str:
    """Returns the name of the next node based on intent and confidence threshold."""
    confidence_threshold = 0.70
    intent = state.get("detected_intent", "Clarification")
    confidence = state.get("confidence_score", 0.0)

    if confidence < confidence_threshold:
        logger.info(f"[{state['request_id']}] Low confidence ({confidence:.2f} < {confidence_threshold}). Routing to ClarificationAgent.")
        return "clarification"

    route_map = {
        "Scheduling": "scheduling",
        "Leave": "leave",
        "Compliance": "compliance",
    }
    target = route_map.get(intent)
    if target:
        return target

    logger.info(f"[{state['request_id']}] Unknown intent '{intent}'. Routing to ClarificationAgent.")
    return "clarification"


# 3. Specialist Agent Nodes
def scheduling_node(state: AgentState) -> Dict[str, Any]:
    """Delegates to the SchedulingAgent and captures the response."""
    logger.info(f"[{state['request_id']}] Routing to Scheduling Agent")
    try:
        response = execute_with_retry(scheduling_agent.run, state['user_input'], state['memory_context'])
        return {"agent_response": response}
    except Exception as e:
        logger.error(f"Scheduling Agent failed: {e}")
        return {"agent_response": "I encountered an error trying to process scheduling. Please try again.", "errors": state.get("errors", []) + [str(e)]}


def leave_node(state: AgentState) -> Dict[str, Any]:
    """Delegates to the LeaveAgent and captures the response."""
    logger.info(f"[{state['request_id']}] Routing to Leave Agent")
    try:
        response = execute_with_retry(leave_agent.run, state['user_input'], state['memory_context'])
        return {"agent_response": response}
    except Exception as e:
        logger.error(f"Leave Agent failed: {e}")
        return {"agent_response": "I encountered an error checking your leave details. Please try again.", "errors": state.get("errors", []) + [str(e)]}


def compliance_node(state: AgentState) -> Dict[str, Any]:
    """Delegates to the ComplianceAgent and captures the response."""
    logger.info(f"[{state['request_id']}] Routing to Compliance Agent")
    try:
        response = execute_with_retry(compliance_agent.run, state['user_input'], state['memory_context'])
        return {"agent_response": response}
    except Exception as e:
        logger.error(f"Compliance Agent failed: {e}")
        return {"agent_response": "I encountered an error verifying compliance guidelines. Please try again.", "errors": state.get("errors", []) + [str(e)]}


def clarification_node(state: AgentState) -> Dict[str, Any]:
    """Delegates to the ClarificationAgent for ambiguous or low-confidence requests."""
    logger.info(f"[{state['request_id']}] Routing to Clarification Agent")
    try:
        response = execute_with_retry(clarification_agent.run, state['user_input'], state['memory_context'])
        return {"agent_response": response}
    except Exception as e:
        logger.error(f"Clarification Agent failed: {e}")
        return {"agent_response": "I'm sorry, I am unable to clarify your request. Could you please specify your query?", "errors": state.get("errors", []) + [str(e)]}


# 4. Save Memory & Consolidate Node
def save_memory_node(state: AgentState) -> Dict[str, Any]:
    """Saves the interaction to STM and conditionally promotes significant facts to LTM.

    Bug fix: removed the redundant sig_score >= 7 guard here — consolidate_to_ltm()
    already enforces the threshold internally via LTM_SIGNIFICANCE_THRESHOLD env var.
    """
    logger.info(f"[{state['request_id']}] Evaluating significance and saving memory")
    try:
        user_input = state['user_input']
        response = state['agent_response']

        # Always save interaction to STM at a low base score (session context)
        execute_with_retry(
            add_memory,
            user_id=state['user_id'],
            content=f"User: {user_input} | Agent: {response}",
            memory_type="short_term",
            significance_score=3,
            session_id=state['session_id']
        )

        # Evaluate significance via LLM/mock
        sig_score, fact = execute_with_retry(llm_provider.evaluate_significance, user_input, response)
        logger.info(f"[{state['request_id']}] Memory significance: Score={sig_score}, Fact='{fact}'")

        # consolidate_to_ltm handles the threshold check internally — no duplicate check here
        if fact and fact != "No significant facts found.":
            execute_with_retry(
                consolidate_to_ltm,
                user_id=state['user_id'],
                session_id=state['session_id'],
                content=fact,
                significance_score=sig_score,
                metadata={"source_request_id": state['request_id']}
            )

        return {}
    except Exception as e:
        logger.error(f"Memory saving node failed: {e}")
        return {"errors": state.get("errors", []) + [str(e)]}


# 5. Append-only Audit Log Node
def write_audit_node(state: AgentState) -> Dict[str, Any]:
    """Writes an immutable audit log entry. Execution time is computed from start_time in state."""
    logger.info(f"[{state['request_id']}] Writing audit log entry")
    try:
        status = "SUCCESS" if not state.get("errors") else "FAILED"
        error_str = "; ".join(state["errors"]) if state.get("errors") else None
        exec_time = (time.time() - state.get("start_time", time.time())) * 1000.0

        execute_with_retry(
            insert_audit_log,
            request_id=state['request_id'],
            user_id=state['user_id'],
            session_id=state['session_id'],
            user_input=state['user_input'],
            detected_intent=state.get("detected_intent", "Clarification"),
            confidence_score=state.get("confidence_score", 0.0),
            routed_agent=state.get("detected_intent", "Clarification") if state.get("confidence_score", 0.0) >= 0.7 else "Clarification",
            retrieved_memory_context=state.get("memory_context"),
            agent_response=state.get("agent_response", "Error occurred during execution."),
            execution_time_ms=exec_time,
            status=status,
            errors=error_str
        )
    except Exception as e:
        logger.critical(f"CRITICAL: Failed to write append-only audit log: {e}")
    return {}


# Define and compile StateGraph
workflow = StateGraph(AgentState)

workflow.add_node("retrieve_memory", retrieve_memory_node)
workflow.add_node("router", router_node)
workflow.add_node("scheduling", scheduling_node)
workflow.add_node("leave", leave_node)
workflow.add_node("compliance", compliance_node)
workflow.add_node("clarification", clarification_node)
workflow.add_node("save_memory", save_memory_node)
workflow.add_node("write_audit", write_audit_node)

workflow.add_edge(START, "retrieve_memory")
workflow.add_edge("retrieve_memory", "router")

workflow.add_conditional_edges(
    "router",
    route_decision,
    {
        "scheduling": "scheduling",
        "leave": "leave",
        "compliance": "compliance",
        "clarification": "clarification",
    }
)

workflow.add_edge("scheduling", "save_memory")
workflow.add_edge("leave", "save_memory")
workflow.add_edge("compliance", "save_memory")
workflow.add_edge("clarification", "save_memory")
workflow.add_edge("save_memory", "write_audit")
workflow.add_edge("write_audit", END)

orchestrator_graph = workflow.compile()


def run_orchestrator(user_id: str, session_id: str, user_input: str) -> Dict[str, Any]:
    """Runs the orchestrated multi-agent pipeline synchronously and returns a structured result dict."""
    start_time = time.time()
    req_id = f"req_{uuid.uuid4().hex[:8]}"

    initial_state: AgentState = {
        "request_id": req_id,
        "user_id": user_id,
        "session_id": session_id,
        "user_input": user_input,
        "detected_intent": "Clarification",
        "confidence_score": 0.0,
        "memory_context": "",
        "agent_response": "",
        "retry_count": 0,
        "start_time": start_time,
        "errors": []
    }

    try:
        final_state = orchestrator_graph.invoke(initial_state)
        execution_time = (time.time() - start_time) * 1000.0
        return {
            "request_id": final_state["request_id"],
            "intent": final_state.get("detected_intent", "Clarification"),
            "confidence": final_state.get("confidence_score", 0.0),
            "response": final_state.get("agent_response", ""),
            "execution_time_ms": execution_time,
            "status": "SUCCESS" if not final_state.get("errors") else "FAILED"
        }
    except Exception as e:
        logger.error(f"Error during orchestrator invocation: {e}")
        execution_time = (time.time() - start_time) * 1000.0
        return {
            "request_id": req_id,
            "intent": "Clarification",
            "confidence": 0.0,
            "response": "I apologize, but I encountered a system issue while processing your request. Please try again shortly.",
            "execution_time_ms": execution_time,
            "status": "FAILED"
        }
