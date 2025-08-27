"""
Natural Language Understanding Module

Purpose: Extract intent and entities from user messages with conversation context.
"""

import json
from typing import Dict, List, Optional, Any
from core.llm_client import LLMClient
from prompts.nlu_prompt import COMBINED_SYSTEM_PROMPT


class EnhancedNLU:
    """Simple NLU module for intent and entity extraction."""

    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    def analyze_message(self, user_message: str, conversation_context: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze user message and extract intent and entities.

        Args:
            user_message: The user's input message
            conversation_context: Recent conversation history

        Returns:
            Dictionary with intent, entities, confidence, and reasoning
        """
        if not user_message or not user_message.strip():
            return self._create_error_response("Empty message")

        try:
            prompt = self._create_prompt(user_message.strip(), conversation_context or [])
            llm_response = self.llm_client.generate(prompt)
            result = self._parse_response(llm_response)
            return self._clean_result(result)
        except Exception as e:
            return self._create_error_response(f"Analysis failed: {str(e)}")

    def _create_prompt(self, user_message: str, conversation_context: List[Dict]) -> str:
        """Create prompt with conversation context."""
        # Get last 3 user messages
        user_messages = [msg.get('content', '') for msg in conversation_context if msg.get('role') == 'user']
        past_messages = (user_messages[-3:] + ['', '', ''])[:3]  # Pad to 3 messages

        # Get last intent
        last_intent = ""
        for msg in reversed(conversation_context):
            if msg.get('role') == 'assistant' and 'nlu_result' in msg:
                last_intent = msg.get('nlu_result', {}).get('current_turn', {}).get('intent', '')
                break

        # Get session entities
        session_entities = {}
        for msg in conversation_context:
            if msg.get('role') == 'assistant' and 'nlu_result' in msg:
                entities = msg.get('nlu_result', {}).get('current_turn', {}).get('entities', {})
                for key, value in entities.items():
                    if value and value != [] and value != "":
                        session_entities[key] = value

        return COMBINED_SYSTEM_PROMPT.format(
            current_message=user_message,
            past_user_msg_1=past_messages[0],
            past_user_msg_2=past_messages[1],
            past_user_msg_3=past_messages[2],
            last_intent=last_intent,
            session_entities_json=json.dumps(session_entities, indent=2)
        )

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse LLM response JSON."""
        cleaned = response.strip()
        if cleaned.startswith('```json'):
            cleaned = cleaned[7:]
        if cleaned.endswith('```'):
            cleaned = cleaned[:-3]

        try:
            return json.loads(cleaned.strip())
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON: {str(e)}")

    def _clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Clean and validate result."""
        valid_intents = ["DISCOVERY", "ORDER", "RETURN", "EXCHANGE", "PAYMENT", "CHITCHAT", "UNKNOWN"]

        # Clean current_turn
        current_turn = result.get('current_turn', {})
        intent = current_turn.get('intent', '').upper()
        current_turn['intent'] = intent if intent in valid_intents else 'UNKNOWN'
        current_turn['confidence'] = max(0.0, min(1.0, current_turn.get('confidence', 0.5)))

        # Ensure entities exist
        entities = current_turn.get('entities', {})
        entity_defaults = {
            'category': None, 'subcategory': None, 'product': None,
            'specifications': [], 'budget': None, 'quantity': None,
            'order_id': None, 'urgency': None, 'comparison_items': [], 'preferences': []
        }
        for key, default in entity_defaults.items():
            entities.setdefault(key, default)
        current_turn['entities'] = entities

        # Clean continuity
        continuity = result.get('continuity', {})
        continuity.setdefault('continuity_type', 'UNCLEAR')
        continuity.setdefault('confidence', 0.5)
        continuity['confidence'] = max(0.0, min(1.0, continuity['confidence']))

        # Clean consistency_checks
        consistency_checks = result.get('consistency_checks', {})
        consistency_checks.setdefault('entity_conflicts_with_session', [])

        return {
            'current_turn': current_turn,
            'continuity': continuity,
            'consistency_checks': consistency_checks
        }

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create error response."""
        return {
            'current_turn': {
                'intent': 'UNKNOWN',
                'sub_intent': None,
                'confidence': 0.0,
                'entities': {
                    'category': None, 'subcategory': None, 'product': None,
                    'specifications': [], 'budget': None, 'quantity': None,
                    'order_id': None, 'urgency': None, 'comparison_items': [], 'preferences': []
                },
                'reasoning': f"Error: {error_message}"
            },
            'continuity': {
                'continuity_type': 'UNCLEAR',
                'confidence': 0.0,
                'reasoning': 'Processing error occurred'
            },
            'consistency_checks': {
                'entity_conflicts_with_session': []
            }
        }

    def extract_entities_only(self, user_message: str) -> Dict[str, Any]:
        """Extract entities without full analysis."""
        prompt = f"""Extract entities from: "{user_message}"
Return JSON: {{"category": null, "subcategory": null, "product": null, "specifications": [], "budget": null, "quantity": null, "order_id": null, "urgency": null, "comparison_items": [], "preferences": []}}"""

        try:
            response = self.llm_client.generate(prompt)
            return self._parse_response(response)
        except:
            return {
                'category': None, 'subcategory': None, 'product': None,
                'specifications': [], 'budget': None, 'quantity': None,
                'order_id': None, 'urgency': None, 'comparison_items': [], 'preferences': []
            }

    def is_confident_prediction(self, result: Dict[str, Any]) -> bool:
        """Check if prediction is confident enough."""
        thresholds = {'ORDER': 0.7, 'PAYMENT': 0.7, 'RETURN': 0.6, 'EXCHANGE': 0.6, 'DISCOVERY': 0.5}
        intent = result.get('current_turn', {}).get('intent', 'UNKNOWN')
        confidence = result.get('current_turn', {}).get('confidence', 0.0)
        return confidence >= thresholds.get(intent, 0.5)

if __name__ == "__main__":
    nlu = EnhancedNLU()

    ques_1 = {
                  "CURRENT_MESSAGE": "Show me gaming laptops under $1500",
                  "PAST_3_USER_MESSAGES": [
                    "I want to buy a laptop",
                    "Preferably Dell or HP",
                    "Make sure it has at least 16GB RAM"
                  ],
                  "last_intent": "DISCOVERY",
                  "session_entities": {
                    "category": "electronics",
                    "subcategory": "laptop",
                    "product": None,
                    "specifications": {"brand: Dell", "RAM: 16GB"},
                    "budget": None,
                    "quantity": 1,
                    "order_id": None,
                    "urgency": None,
                    "comparison_items": [],
                    "preferences": []
                  }
                }
    ans1 = nlu.analyze_message(str(ques_1))
    print(ans1)

    # ans2 = nlu.analyze_message("I want to buy a laptop with 16GB RAM")
    # ans3 = nlu.analyze_message("I want to buy a laptop with 16GB RAM and 1TB SSD")
    # chk=1

