from typing import Dict, Any
from utils.llm import LLMProvider

class LeaveAgent:
    """Specialist agent stub for leave balance checks, vacation bookings, and sick leaves."""
    
    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    def run(self, user_input: str, memory_context: str) -> str:
        """Executes logic for Leave requests and returns the response."""
        return self.llm_provider.generate_agent_response("Leave", user_input, memory_context)
