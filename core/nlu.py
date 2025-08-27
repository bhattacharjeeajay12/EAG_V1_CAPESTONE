"""
Natural Language Understanding Module

Purpose: Extract intent and entities from user messages with conversation context.
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any

from core.llm_client import LLMClient
from prompts.nlu_prompt import COMBINED_SYSTEM_PROMPT


class EnhancedNLU:
    """NLU module for intent and entity extraction."""

    # ---- Constants ----
    ENTITY_DEFAULTS: Dict[str, Any] = {
        "category": None,
        "subcategory": None,
        "product": None,
        "specifications": [],
        "budget": None,
        "quantity": None,
        "order_id": None,
        "urgency": None,
        "comparison_items": [],
        "preferences": []
    }

    VALID_INTENTS = {
        "DISCOVERY", "ORDER", "RETURN", "EXCHANGE",
        "PAYMENT", "CHITCHAT", "UNKNOWN"
    }

    INTENT_THRESHOLDS = {
        "ORDER": 0.7,
        "PAYMENT": 0.7,
        "RETURN": 0.6,
        "EXCHANGE": 0.6,
        "DISCOVERY": 0.5
    }

    # ---- Init ----
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    # ---- Public Methods ----
    def analyze_message(
        self, user_message: str,
        conversation_context: Optional[List[Dict[str, Any]]] = None
    ) -> Dict[str, Any]:
        """Analyze user message and extract intent + entities."""
        if not user_message or not user_message.strip():
            return self._create_error_response("Empty message")

        try:
            prompt = self._create_prompt(user_message.strip(), conversation_context or [])
            llm_response = self.llm_client.generate(prompt)
            result = self._parse_response(llm_response)
            return self._clean_result(result)
        except Exception as e:
            return self._create_error_response(f"Analysis failed: {str(e)}")

    def extract_entities_only(self, user_message: str) -> Dict[str, Any]:
        """Extract entities without full analysis."""
        prompt = f"""Extract entities from: "{user_message}"
Return JSON: {json.dumps(self.ENTITY_DEFAULTS)}"""

        try:
            response = self.llm_client.generate(prompt)
            return self._parse_response(response)
        except Exception:
            return dict(self.ENTITY_DEFAULTS)

    def is_confident_prediction(self, result: Dict[str, Any]) -> bool:
        """Check if prediction confidence exceeds threshold."""
        intent = result.get("current_turn", {}).get("intent", "UNKNOWN")
        confidence = result.get("current_turn", {}).get("confidence", 0.0)
        return confidence >= self.INTENT_THRESHOLDS.get(intent, 0.5)

    # ---- Internal Helpers ----
    def _create_prompt(self, user_message: str, conversation_context: List[Dict[str, Any]]) -> str:
        """Create system prompt with conversation context."""
        # Last 3 user messages
        user_messages = [msg.get("content", "") for msg in conversation_context if msg.get("role") == "user"]
        past_messages = (user_messages[-3:] + ["", "", ""])[:3]

        # Last intent
        last_intent = ""
        for msg in reversed(conversation_context):
            if msg.get("role") == "assistant" and "nlu_result" in msg:
                last_intent = msg["nlu_result"].get("current_turn", {}).get("intent", "")
                break

        # Session entities
        session_entities: Dict[str, Any] = {}
        for msg in conversation_context:
            if msg.get("role") == "assistant" and "nlu_result" in msg:
                entities = msg["nlu_result"].get("current_turn", {}).get("entities", {})
                for k, v in entities.items():
                    if v not in (None, [], ""):
                        session_entities[k] = v

        return COMBINED_SYSTEM_PROMPT.format(
            current_message=user_message,
            past_user_msg_1=past_messages[0],
            past_user_msg_2=past_messages[1],
            past_user_msg_3=past_messages[2],
            last_intent=last_intent,
            session_entities_json=json.dumps(session_entities, indent=2)
        )

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response as JSON."""
        cleaned = (
            response.strip()
            .removeprefix("```json")
            .removesuffix("```")
            .strip()
        )
        return json.loads(cleaned)

    def _clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and normalize result."""
        current_turn = result.get("current_turn", {})
        intent = current_turn.get("intent", "").upper()
        current_turn["intent"] = intent if intent in self.VALID_INTENTS else "UNKNOWN"
        current_turn["confidence"] = max(0.0, min(1.0, current_turn.get("confidence", 0.5)))
        current_turn["entities"] = {**self.ENTITY_DEFAULTS, **current_turn.get("entities", {})}

        continuity = {**{"continuity_type": "UNCLEAR", "confidence": 0.5}, **result.get("continuity", {})}
        continuity["confidence"] = max(0.0, min(1.0, continuity["confidence"]))

        consistency_checks = {**{"entity_conflicts_with_session": []}, **result.get("consistency_checks", {})}

        return {
            "current_turn": current_turn,
            "continuity": continuity,
            "consistency_checks": consistency_checks
        }

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Return fallback response in case of failure."""
        return {
            "current_turn": {
                "intent": "UNKNOWN",
                "sub_intent": None,
                "confidence": 0.0,
                "entities": dict(self.ENTITY_DEFAULTS),
                "reasoning": f"Error: {error_message}"
            },
            "continuity": {
                "continuity_type": "UNCLEAR",
                "confidence": 0.0,
                "reasoning": "Processing error occurred"
            },
            "consistency_checks": {
                "entity_conflicts_with_session": []
            }
        }

    def _reorder_answer(self, answer: Dict[str, Any]) -> Dict[str, Any]:
        """Ensure question_key and question are the first keys."""
        order = ["question_key", "question"]
        return {k: answer[k] for k in order if k in answer} | {
            k: v for k, v in answer.items() if k not in order
        }


# ---- Script Mode ----
if __name__ == "__main__":
    from tests.nlu.nlu_questions import questions

    nlu = EnhancedNLU()
    answers = []

    for idx, (key, value) in enumerate(questions.items(), start=1):
        answer = nlu.analyze_message(value["CURRENT_MESSAGE"])
        answer["question"] = value["CURRENT_MESSAGE"]
        answer["question_key"] = key
        answers.append(nlu._reorder_answer(answer))
        print(f"Question {idx}: is done")

    output_file = Path("tests") / "nlu" / "nlu_answers.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)  # ensure dir exists
    with output_file.open("w") as f:
        json.dump(answers, f, indent=2)
