from typing import Dict, Any, Tuple
from utils.llm import LLMProvider

class IntentRouter:
    """Classifies user queries to decide which specialist agent receives the workflow."""
    
    def __init__(self, llm_provider: LLMProvider) -> None:
        self.llm_provider = llm_provider

    def route_query(self, user_input: str) -> Tuple[str, float]:
        """Returns the classified intent and its confidence score."""
        return self.llm_provider.classify_intent(user_input)
