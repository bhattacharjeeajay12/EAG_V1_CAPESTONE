#core/planner_nlu.py
"""
Natural Language Understanding Module
"""

import json
import time
from pathlib import Path
from typing import Dict, List, Optional, Any
from core.llm_client import LLMClient
from prompts.discovery import SYSTEM_PROMPT
import os
from dotenv import load_dotenv
load_dotenv()

class DiscoveryNLU:
    """Simple nlu for intent and entity extraction."""

    ENTITY_DEFAULTS = {
        "category": [],
        "subcategory": []
    }

    def __init__(self, llm_client: Optional[LLMClient] = None):
        # self.llm_client = llm_client or LLMClient(model_type=os.getenv("MODEL_TYPE", "openai"))
        model_type = os.getenv("MODEL_TYPE", "gpt-3.5")  # Use a supported default
        self.llm_client = llm_client or LLMClient(model_type=model_type)
    async def analyze_message(self, user_message: str, conversation_context: Optional[List[Dict[str, Any]]] = None, last_intent: str = "", session_entities: Dict = None) -> Dict[str, Any]:
        """Analyze user message and return intent + entities."""
        if not user_message.strip():
            return self._error_response("Empty message")
        try:
            user_prompt = self._create_user_prompt(user_message.strip(), conversation_context or [], last_intent, session_entities or {})
            response = await self.llm_client.generate(SYSTEM_PROMPT, user_prompt)  # Make this call async
            result = self._parse_json(response)
            return self._clean_result(result)
        except Exception as e:
            print(f"Error: {e}")
            return self._error_response(str(e))

    def _create_user_prompt(self, user_message: str, conversation_context: List[Dict[str, Any]], last_intent: str, session_entities: Dict) -> str:
        """Create user prompt with context data."""
        # Get past user messages
        user_messages = [msg.get("content", "") for msg in conversation_context if msg.get("role") == "user"]
        past_messages = (user_messages[-3:] + ["", "", ""])[:3]

        return f"""
CURRENT_MESSAGE: {user_message}
PAST_3_USER_MESSAGES:
  1. {past_messages[0]}
  2. {past_messages[1]}
  3. {past_messages[2]}
LAST_INTENT: {last_intent}
SESSION_ENTITIES_SO_FAR: {json.dumps(session_entities, indent=2)}
"""

    def _parse_json(self, response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response."""
        text = response.strip()

        # Remove code fences
        if text.startswith("```"):
            lines = text.split('\n')
            text = '\n'.join(line for line in lines if not line.strip().startswith("```"))

        # Clean trailing commas
        import re
        text = re.sub(r',\s*}', '}', text)
        text = re.sub(r',\s*]', ']', text)

        # Find JSON boundaries
        start = text.find('{')
        end = text.rfind('}')
        if start == -1 or end == -1:
            raise ValueError("No JSON found")

        json_text = text[start:end + 1]
        return json.loads(json_text)

    def _clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate result."""
        # Ensure structure exists
        if "current_turn" not in result:
            result["current_turn"] = {}
        if "continuity" not in result:
            result["continuity"] = {}

        # Clean entities
        current_turn = result["current_turn"]
        entities = {**self.ENTITY_DEFAULTS, **current_turn.get("entities", {})}

        # Ensure specifications is dict
        if not isinstance(entities.get("specifications"), dict):
            entities["specifications"] = {}

        current_turn["entities"] = entities
        return result

    def _error_response(self, error: str) -> Dict[str, Any]:
        """Return error response."""
        return {
            "current_turn": {
                "confidence": 0.0,
                "entities": dict(self.ENTITY_DEFAULTS),
                "intent": "UNKNOWN",
                "reasoning": f"Error: {error}"
            },
            "continuity": {
                "continuity_type": "UNCLEAR",
                "confidence": 0.0,
                "reasoning": "Processing error",
                "sub_intent": "NULL"
            },
            "is_error": True
        }


# Create a new testing script: tests/test_nlu.py
