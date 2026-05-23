import os
import re
import json
from typing import Dict, Any, Tuple, Optional
import urllib.request
import urllib.error

class LLMProvider:
    """Unified LLM service. Supports real OpenAI/Gemini REST endpoints and a robust offline mock fallback."""
    
    def __init__(self) -> None:
        self.provider = os.getenv("LLM_PROVIDER", "mock").lower()
        self.openai_key = os.getenv("OPENAI_API_KEY", "").strip()
        self.gemini_key = os.getenv("GEMINI_API_KEY", "").strip()

    def classify_intent(self, text: str) -> Tuple[str, float]:
        """Classifies user input text into: Scheduling, Leave, Compliance, Clarification."""
        if self.provider == "openai" and self.openai_key:
            try:
                return self._openai_classify_intent(text)
            except Exception as e:
                # Fallback to mock on error
                pass
        elif self.provider == "gemini" and self.gemini_key:
            try:
                return self._gemini_classify_intent(text)
            except Exception as e:
                pass
        
        return self._mock_classify_intent(text)

    def evaluate_significance(self, user_input: str, agent_response: str) -> Tuple[int, str]:
        """Evaluates significance (1-10) and extracts core facts for LTM promotion."""
        if self.provider == "openai" and self.openai_key:
            try:
                return self._openai_evaluate_significance(user_input, agent_response)
            except Exception as e:
                pass
        elif self.provider == "gemini" and self.gemini_key:
            try:
                return self._gemini_evaluate_significance(user_input, agent_response)
            except Exception as e:
                pass

        return self._mock_evaluate_significance(user_input, agent_response)

    def generate_agent_response(self, agent_name: str, user_input: str, memory_context: str) -> str:
        """Generates sub-agent response text incorporating user input and history context."""
        if self.provider == "openai" and self.openai_key:
            try:
                return self._openai_generate_agent_response(agent_name, user_input, memory_context)
            except Exception as e:
                pass
        elif self.provider == "gemini" and self.gemini_key:
            try:
                return self._gemini_generate_agent_response(agent_name, user_input, memory_context)
            except Exception as e:
                pass

        return self._mock_generate_agent_response(agent_name, user_input, memory_context)

    # --- MOCK IMPLEMENTATIONS ---
    
    def _mock_classify_intent(self, text: str) -> Tuple[str, float]:
        text_lower = text.lower()
        
        sched_keywords = ["schedule", "book", "meeting", "calendar", "interview", "appointment", "slot", "tomorrow", "am", "pm", "invite"]
        leave_keywords = ["leave", "vacation", "sick", "off", "holiday", "pto", "time off"]
        comp_keywords = ["policy", "compliance", "regulation", "handbook", "rules", "guideline", "legal", "remote work", "dress code", "conduct", "harassment"]
        
        sched_score = sum(1 for kw in sched_keywords if kw in text_lower)
        leave_score = sum(1 for kw in leave_keywords if kw in text_lower)
        comp_score = sum(1 for kw in comp_keywords if kw in text_lower)
        
        # Dynamic confidence boosting
        max_score = max(sched_score, leave_score, comp_score)
        if max_score == 0:
            return "Clarification", 0.50
            
        if sched_score == max_score:
            confidence = min(0.70 + (sched_score * 0.08), 0.98)
            return "Scheduling", confidence
        elif leave_score == max_score:
            confidence = min(0.70 + (leave_score * 0.08), 0.98)
            return "Leave", confidence
        else:
            confidence = min(0.70 + (comp_score * 0.08), 0.98)
            return "Compliance", confidence

    def _mock_evaluate_significance(self, user_input: str, agent_response: str) -> Tuple[int, str]:
        text = (user_input + " " + agent_response).lower()
        extracted_facts = []
        score = 3
        
        # Search for name preferences
        pref_match = re.search(r"prefer\s+([a-zA-Z0-9_\-\s]+)", text)
        mgr_match = re.search(r"manager\s+(?:is|has\s+been|changed\s+to)\s+([a-zA-Z]+)", text)
        date_match = re.search(r"(?:from|on|between)\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?|\d{4}-\d{2}-\d{2})", text)
        email_match = re.search(r"[\w\.-]+@[\w\.-]+\.\w+", text)
        
        if mgr_match:
            extracted_facts.append(f"User's manager is {mgr_match.group(1).title()}.")
            score = max(score, 8)
        if pref_match:
            extracted_facts.append(f"User prefers: {pref_match.group(1).strip()}.")
            score = max(score, 7)
        if date_match and ("leave" in text or "vacation" in text):
            extracted_facts.append(f"User requested leave dates starting: {date_match.group(1)}.")
            score = max(score, 7)
        if email_match:
            extracted_facts.append(f"User email address is {email_match.group(0)}.")
            score = max(score, 8)
            
        if "approved" in agent_response.lower() and "leave" in text:
            extracted_facts.append("System processed and approved a leave request.")
            score = max(score, 9)
            
        fact_str = " ".join(extracted_facts) if extracted_facts else "No significant facts found."
        return score, fact_str

    def _mock_generate_agent_response(self, agent_name: str, user_input: str, memory_context: str) -> str:
        # Check context to see if there is relevant history to inject
        history_note = ""
        if "preference" in memory_context.lower() or "prefers" in memory_context.lower():
            history_note = " (Context: Applying your saved preferences)"
        if "manager" in memory_context.lower():
            history_note += " (Context: Noting your manager's details)"
            
        if agent_name == "Scheduling":
            return f"Scheduling Agent: I have processed your request '{user_input}'.{history_note} [Stub Action: Simulated calendar invite sent for meeting]"
        elif agent_name == "Leave":
            return f"Leave Agent: I have recorded your leave query '{user_input}'.{history_note} [Stub Action: Leave balance verified and entry created]"
        elif agent_name == "Compliance":
            return f"Compliance Agent: Regarding '{user_input}', ZeloraTech HR Guidelines (Section 4.1) state that employees must comply with all remote-work, code of conduct, and reporting standards."
        elif agent_name == "Clarification":
            return f"Orchestrator: I'm not fully certain about your request '{user_input}'. Could you please clarify if this is about booking a meeting, requesting leaves, or querying policy compliance?"
        else:
            return "Orchestrator: Specialist agent is unavailable. Your request has been queued."

    # --- OPENAI API CALLS ---
    
    def _openai_api_call(self, prompt: str, system_prompt: str) -> str:
        url = "https://api.openai.com/v1/chat/completions"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.openai_key}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt}
            ],
            "temperature": 0.2
        }
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=30) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res["choices"][0]["message"]["content"].strip()

    def _openai_classify_intent(self, text: str) -> Tuple[str, float]:
        sys = "You are an HR request classifier. Classify the user text into exactly one of: Scheduling, Leave, Compliance, Clarification. Respond ONLY with a valid JSON object: {\"intent\": \"<intent>\", \"confidence\": <float_0_to_1>}"
        raw = self._openai_api_call(text, sys)
        # Parse JSON
        parsed = json.loads(raw)
        return parsed["intent"], float(parsed["confidence"])

    def _openai_evaluate_significance(self, user_input: str, agent_response: str) -> Tuple[int, str]:
        sys = "You are an HR memory assessor. Review the user request and agent response. Determine if any facts should be stored in the User's Long-Term Memory (e.g. manager, preferences, dates of approved leaves). Respond ONLY with valid JSON: {\"score\": <int_1_to_10>, \"extracted_fact\": \"<string_summary_or_empty>\"}"
        prompt = f"User input: {user_input}\nAgent response: {agent_response}"
        raw = self._openai_api_call(prompt, sys)
        parsed = json.loads(raw)
        return int(parsed["score"]), parsed["extracted_fact"]

    def _openai_generate_agent_response(self, agent_name: str, user_input: str, memory_context: str) -> str:
        sys = f"You are the {agent_name} HR Agent. Respond to the user's request. Memory Context from previous sessions: {memory_context}"
        return self._openai_api_call(user_input, sys)

    # --- GEMINI API CALLS ---
    
    def _gemini_api_call(self, prompt: str, system_prompt: str) -> str:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={self.gemini_key}"
        headers = {"Content-Type": "application/json"}
        # Combine system prompt and user prompt
        full_prompt = f"{system_prompt}\n\nUser request: {prompt}"
        data = {
            "contents": [
                {"parts": [{"text": full_prompt}]}
            ]
        }
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers)
        with urllib.request.urlopen(req, timeout=8) as response:
            res = json.loads(response.read().decode("utf-8"))
            return res["candidates"][0]["content"]["parts"][0]["text"].strip()

    def _gemini_classify_intent(self, text: str) -> Tuple[str, float]:
        sys = "You are an HR request classifier. Classify the user text into exactly one of: Scheduling, Leave, Compliance, Clarification. Respond ONLY with a JSON block: {\"intent\": \"<intent>\", \"confidence\": <float_0_to_1>}"
        raw = self._gemini_api_call(text, sys)
        # Handle cases where markdown wrapping is returned
        cleaned = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(cleaned)
        return parsed["intent"], float(parsed["confidence"])

    def _gemini_evaluate_significance(self, user_input: str, agent_response: str) -> Tuple[int, str]:
        sys = "You are an HR memory assessor. Review the user request and agent response. Determine if any facts should be stored in the User's Long-Term Memory (e.g. manager, preferences, dates of approved leaves). Respond ONLY with valid JSON: {\"score\": <int_1_to_10>, \"extracted_fact\": \"<string_summary_or_empty>\"}"
        prompt = f"User input: {user_input}\nAgent response: {agent_response}"
        raw = self._gemini_api_call(prompt, sys)
        cleaned = re.sub(r"```json|```", "", raw).strip()
        parsed = json.loads(cleaned)
        return int(parsed["score"]), parsed["extracted_fact"]

    def _gemini_generate_agent_response(self, agent_name: str, user_input: str, memory_context: str) -> str:
        sys = f"You are the {agent_name} HR Agent. Respond to the user's request. Memory Context from previous sessions: {memory_context}"
        return self._gemini_api_call(user_input, sys)
