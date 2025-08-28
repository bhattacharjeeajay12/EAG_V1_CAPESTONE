"""
Natural Language Understanding Module
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from core.llm_client import LLMClient
from prompts.nlu_prompt import COMBINED_SYSTEM_PROMPT

from dotenv import load_dotenv
load_dotenv()

class EnhancedNLU:
    """Simple NLU for intent and entity extraction."""

    ENTITY_DEFAULTS = {
        "category": None,
        "subcategory": None,
        "product": None,
        "specifications": {},
        "budget": None,
        "quantity": None,
        "order_id": None,
        "urgency": None,
        "comparison_items": [],
        "preferences": []
    }

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def _create_prompt(self, user_message: str, conversation_context: List[Dict[str, Any]]) -> str:
        """Create prompt with context."""
        # Get past user messages
        user_messages = [msg.get("content", "") for msg in conversation_context if msg.get("role") == "user"]
        past_messages = (user_messages[-3:] + ["", "", ""])[:3]

        return COMBINED_SYSTEM_PROMPT.format(
            current_message=user_message,
            past_user_msg_1=past_messages[0],
            past_user_msg_2=past_messages[1],
            past_user_msg_3=past_messages[2],
            last_intent="",
            session_entities_json="{}"
        )

    def analyze_message(self, user_message: str, conversation_context: Optional[List[Dict[str, Any]]] = None,
                        last_intent: str = "", session_entities: Dict = None) -> Dict[str, Any]:
        """Analyze user message and return intent + entities."""
        if not user_message.strip():
            return self._error_response("Empty message")

        try:
            prompt = self._create_prompt_with_context(user_message.strip(), conversation_context or [], last_intent,
                                                      session_entities or {})
            response = self.llm_client.generate(prompt)
            result = self._parse_json(response)
            return self._clean_result(result)
        except Exception as e:
            print(f"Error: {e}")
            return self._error_response(str(e))

    def _create_prompt_with_context(self, user_message: str, conversation_context: List[Dict[str, Any]],
                                    last_intent: str, session_entities: Dict) -> str:
        """Create prompt with all context."""
        # Get past user messages
        user_messages = [msg.get("content", "") for msg in conversation_context if msg.get("role") == "user"]
        past_messages = (user_messages[-3:] + ["", "", ""])[:3]

        return COMBINED_SYSTEM_PROMPT.format(
            current_message=user_message,
            past_user_msg_1=past_messages[0],
            past_user_msg_2=past_messages[1],
            past_user_msg_3=past_messages[2],
            last_intent=last_intent,
            session_entities_json=json.dumps(session_entities, indent=2)
        )

    def _parse_json(self, response: str) -> Dict[str, Any]:
        """Extract JSON from LLM response."""
        text = response.strip()

        # Remove code fences
        if text.startswith("```"):
            lines = text.split('\n')
            text = '\n'.join(line for line in lines if not line.strip().startswith("```"))

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
        if "consistency_checks" not in result:
            result["consistency_checks"] = {}

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
                "intent": "UNKNOWN",
                "sub_intent": None,
                "confidence": 0.0,
                "entities": dict(self.ENTITY_DEFAULTS),
                "reasoning": f"Error: {error}"
            },
            "continuity": {
                "continuity_type": "UNCLEAR",
                "confidence": 0.0,
                "reasoning": "Processing error"
            },
            "consistency_checks": {
                "entity_conflicts_with_session": []
            }
        }


if __name__ == "__main__":
    from tests.nlu.nlu_questions import questions

    nlu = EnhancedNLU()
    answers = []

    for idx, (key, value) in enumerate(questions.items(), start=1):
        past_messages = []
        for msg in value.get("PAST_3_USER_MESSAGES", []):
            past_messages.append({"role": "user", "content": msg})

        answer = nlu.analyze_message(
            value["CURRENT_MESSAGE"],
            past_messages,
            value.get("last_intent", ""),
            value.get("session_entities", {})
        )
        answer["question"] = value["CURRENT_MESSAGE"]
        answer["question_key"] = key
        answers.append(answer)
        print(f"Question {idx}: done")

    # Save results
    output_file = Path("tests") / "nlu" / "nlu_answers.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    with output_file.open("w") as f:
        json.dump(answers, f, indent=2)