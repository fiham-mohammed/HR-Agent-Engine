from typing import Dict, Any
from utils.llm import LLMProvider

class ComplianceAgent:
    """Specialist agent stub for company policies, legal compliance, and handbook queries."""
    
    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    def run(self, user_input: str, memory_context: str) -> str:
        """Executes logic for Compliance/Policy queries and returns the response."""
        return self.llm_provider.generate_agent_response("Compliance", user_input, memory_context)
