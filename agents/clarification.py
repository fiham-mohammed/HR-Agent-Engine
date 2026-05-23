from typing import Dict, Any
from utils.llm import LLMProvider

class ClarificationAgent:
    """Fallback agent for ambiguous requests, low confidence intent classifications, and generic inputs."""
    
    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    def run(self, user_input: str, memory_context: str) -> str:
        """Asks the user for clarification in a polite and helpful manner."""
        return self.llm_provider.generate_agent_response("Clarification", user_input, memory_context)
