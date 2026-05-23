from typing import Dict, Any
from utils.llm import LLMProvider

class SchedulingAgent:
    """Specialist agent stub for meeting requests, interview schedules, and calendar management."""
    
    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    def run(self, user_input: str, memory_context: str) -> str:
        """Executes logic for Scheduling and returns the response."""
        return self.llm_provider.generate_agent_response("Scheduling", user_input, memory_context)
