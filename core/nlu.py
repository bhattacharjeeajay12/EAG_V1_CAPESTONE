# core_1/enhanced_nlu.py
"""
Natural Language Understanding Module

Purpose: Focused on pure language understanding - intent tracking, extracting intents and entities from
from user messages without making conversation flow decisions. This module
provides clean, structured output for the Planner to make routing decisions.

Key Responsibilities:
- Intent classification (BUY, ORDER, RECOMMEND, RETURN)
- Entity extraction (category, subcategory, budget, order_id, etc.)
- Confidence scoring
- Intent tracking (Intent tracking)
- Clean, structured output format

Does NOT handle:
- Conversation flow decisions (Planner's job)
- Context management (Context Manager's job)
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()

import json
from typing import Dict, List, Optional, Any
from enum import Enum
from core.llm_client import LLMClient
from prompts.nlu_prompt import COMBINED_SYSTEM_PROMPT

class IntentStatus(Enum):
    """Status of tracked intents."""
    ACTIVE = "active"  # Currently being worked on
    CHANGE = "change"  # change paused
    COMPLETED = "completed"  # Successfully finished
    ABANDONED = "abandoned"  # User cancelled/switched away


class EnhancedNLU:
    """
    Pure NLU module focused on understanding user messages.

    This module analyzes user input and returns structured information
    about what the user wants (intent), relevant details (entities) and intent tracking.
    It stays focused on language understanding without making decisions
    about conversation flow or intent transitions.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize Enhanced NLU module.

        Args:
            llm_client: LLM client for processing. If None, creates default client.
        """
        self.llm_client = llm_client or LLMClient()
        self.valid_intents = ["DISCOVERY", "ORDER", "RETURN", "EXCHANGE", "PAYMENT", "CHITCHAT", "UNKNOWN"]
        self.valid_sub_intents = {
            "DISCOVERY": ["explore", "compare", "decide", "purchase"],
            "ORDER": ["check_status", "modify", "cancel", "track"],
            "RETURN": ["initiate", "status", "refund_status"],
            "EXCHANGE": ["initiate", "status"],
            "PAYMENT": ["select_method", "complete", "resolve_issue"],
            "CHITCHAT": [],
            "UNKNOWN": []
        }
        self.valid_continuity_types = ["CONTINUATION", "INTENT_SWITCH", "CONTEXT_SWITCH", "ADDITION", "UNCLEAR"]
        self.valid_context_switch_options = ["REPLACE", "ADD", "COMPARE", "SEPARATE"]

    def analyze_message(self, user_message: str, conversation_context: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze user message and extract intent and entities.

        Args:
            user_message: The user's input message
            conversation_context: Recent conversation history for context

        Returns:
            Dictionary with intent, entities, confidence, and reasoning
        """
        try:
            # Validate input
            if not user_message or not user_message.strip():
                return self._create_error_response("Empty or invalid user message")

            # Create LLM prompt for pure NLU analysis
            prompt = self._create_nlu_prompt(user_message.strip(), conversation_context or [])

            # Get LLM response
            llm_response = self.llm_client.generate(prompt)

            # Parse and validate response
            result = self._parse_llm_response(llm_response)

            return self._validate_and_clean_result(result)

        except Exception as e:
            return self._create_error_response(f"NLU analysis failed: {str(e)}")

    def _create_nlu_prompt(self, user_message: str, conversation_context: List[Dict]) -> str:
        """Create prompt for LLM analysis using the combined system prompt."""

        # Extract context information
        past_messages = [""] * 3  # Initialize with empty strings
        last_intent = ""
        session_entities = {}

        # Get the last 3 user messages and last intent
        user_messages = [msg for msg in conversation_context if msg.get('role') == 'user']
        if user_messages:
            # Get last 3 user messages (oldest to newest)
            recent_user_messages = user_messages[-3:]
            for i, msg in enumerate(recent_user_messages):
                if i < 3:
                    past_messages[i] = msg.get('content', '')

        # Get last intent from assistant messages with NLU results
        for msg in reversed(conversation_context):
            if msg.get('role') == 'assistant' and 'nlu_result' in msg:
                nlu_result = msg.get('nlu_result', {})
                current_turn = nlu_result.get('current_turn', {})
                if current_turn.get('intent'):
                    last_intent = current_turn['intent']
                    break

        # Accumulate session entities (simplified - in practice this would be more sophisticated)
        for msg in conversation_context:
            if msg.get('role') == 'assistant' and 'nlu_result' in msg:
                nlu_result = msg.get('nlu_result', {})
                current_turn = nlu_result.get('current_turn', {})
                entities = current_turn.get('entities', {})
                # Merge non-null entities
                for key, value in entities.items():
                    if value is not None and value != [] and value != "":
                        session_entities[key] = value

        # Format the prompt
        prompt = COMBINED_SYSTEM_PROMPT.format(
            current_message=user_message,
            past_user_msg_1=past_messages[0],
            past_user_msg_2=past_messages[1],
            past_user_msg_3=past_messages[2],
            last_intent=last_intent,
            session_entities_json=json.dumps(session_entities, indent=2)
        )

        return prompt

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """Parse and validate LLM response JSON."""
        try:
            # Clean the response - remove any markdown formatting
            cleaned_response = llm_response.strip()
            if cleaned_response.startswith('```json'):
                cleaned_response = cleaned_response[7:]
            if cleaned_response.endswith('```'):
                cleaned_response = cleaned_response[:-3]
            cleaned_response = cleaned_response.strip()

            # Parse JSON
            result = json.loads(cleaned_response)
            return result

        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid JSON response from LLM: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error parsing LLM response: {str(e)}")

    def _validate_and_clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and clean the parsed result."""
        try:
            # Validate main structure
            if not isinstance(result, dict):
                raise ValueError("Result must be a dictionary")

            # Validate current_turn
            current_turn = result.get('current_turn', {})
            if not isinstance(current_turn, dict):
                raise ValueError("current_turn must be a dictionary")

            # Validate intent
            intent = current_turn.get('intent', '').upper()
            if intent not in self.valid_intents:
                intent = 'UNKNOWN'
            current_turn['intent'] = intent

            # Validate sub_intent
            sub_intent = current_turn.get('sub_intent')
            if sub_intent and intent in self.valid_sub_intents:
                if sub_intent not in self.valid_sub_intents[intent]:
                    sub_intent = None
            current_turn['sub_intent'] = sub_intent

            # Validate confidence
            confidence = current_turn.get('confidence', 0.0)
            if not isinstance(confidence, (int, float)) or confidence < 0 or confidence > 1:
                confidence = 0.5
            current_turn['confidence'] = float(confidence)

            # Validate entities structure
            entities = current_turn.get('entities', {})
            if not isinstance(entities, dict):
                entities = {}

            # Ensure all expected entity keys exist
            expected_entities = [
                'category', 'subcategory', 'product', 'specifications',
                'budget', 'quantity', 'order_id', 'urgency',
                'comparison_items', 'preferences'
            ]
            for key in expected_entities:
                if key not in entities:
                    if key in ['specifications', 'comparison_items', 'preferences']:
                        entities[key] = []
                    else:
                        entities[key] = None

            # Validate urgency values
            if entities.get('urgency') and entities['urgency'] not in ['low', 'medium', 'high', 'asap']:
                entities['urgency'] = None

            current_turn['entities'] = entities

            # Ensure reasoning exists
            if not current_turn.get('reasoning'):
                current_turn['reasoning'] = "Intent and entities extracted from user message"

            # Validate continuity
            continuity = result.get('continuity', {})
            if not isinstance(continuity, dict):
                continuity = {}

            continuity_type = continuity.get('continuity_type', 'UNCLEAR')
            if continuity_type not in self.valid_continuity_types:
                continuity_type = 'UNCLEAR'
            continuity['continuity_type'] = continuity_type

            # Validate continuity confidence
            continuity_confidence = continuity.get('confidence', 0.5)
            if not isinstance(continuity_confidence,
                              (int, float)) or continuity_confidence < 0 or continuity_confidence > 1:
                continuity_confidence = 0.5
            continuity['confidence'] = float(continuity_confidence)

            if not continuity.get('reasoning'):
                continuity['reasoning'] = "Continuity analysis based on conversation context"

            # Validate context_switch_options
            if continuity_type == 'CONTEXT_SWITCH':
                options = continuity.get('context_switch_options', [])
                if not isinstance(options, list):
                    options = []
                # Filter to valid options
                options = [opt for opt in options if opt in self.valid_context_switch_options]
                continuity['context_switch_options'] = options
            else:
                continuity.pop('context_switch_options', None)

            # Handle suggested_clarification for UNCLEAR continuity
            if continuity_type == 'UNCLEAR' and not continuity.get('suggested_clarification'):
                continuity['suggested_clarification'] = "Could you please clarify what you're looking for?"
            elif continuity_type != 'UNCLEAR':
                continuity.pop('suggested_clarification', None)

            # Validate consistency_checks
            consistency_checks = result.get('consistency_checks', {})
            if not isinstance(consistency_checks, dict):
                consistency_checks = {}

            conflicts = consistency_checks.get('entity_conflicts_with_session', [])
            if not isinstance(conflicts, list):
                conflicts = []
            consistency_checks['entity_conflicts_with_session'] = conflicts

            # Assemble final result
            final_result = {
                'current_turn': current_turn,
                'continuity': continuity,
                'consistency_checks': consistency_checks
            }

            return final_result

        except Exception as e:
            return self._create_error_response(f"Validation error: {str(e)}")

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """Create a standardized error response."""
        return {
            'current_turn': {
                'intent': 'UNKNOWN',
                'sub_intent': None,
                'confidence': 0.0,
                'entities': {
                    'category': None,
                    'subcategory': None,
                    'product': None,
                    'specifications': [],
                    'budget': None,
                    'quantity': None,
                    'order_id': None,
                    'urgency': None,
                    'comparison_items': [],
                    'preferences': []
                },
                'reasoning': f"Error in NLU processing: {error_message}"
            },
            'continuity': {
                'continuity_type': 'UNCLEAR',
                'confidence': 0.0,
                'reasoning': 'Unable to determine continuity due to processing error',
                'suggested_clarification': 'I had trouble understanding your message. Could you please rephrase?'
            },
            'consistency_checks': {
                'entity_conflicts_with_session': [],
                'notes': f'Error occurred: {error_message}'
            }
        }

    def extract_entities_only(self, user_message: str) -> Dict[str, Any]:
        """
        Extract just entities from a message without full NLU analysis.
        Useful for quick entity extraction without conversation context.
        """
        try:
            # Simple entity extraction prompt
            prompt = f"""Extract entities from this e-commerce message: "{user_message}"

Return JSON with these entities (set to null if not found):
{{
    "category": null,
    "subcategory": null, 
    "product": null,
    "specifications": [],
    "budget": null,
    "quantity": null,
    "order_id": null,
    "urgency": null,
    "comparison_items": [],
    "preferences": []
}}

Budget format: "$100" or "$100-$200"
Urgency values: "low", "medium", "high", "asap"
"""

            response = self.llm_client.generate(prompt)
            entities = self._parse_llm_response(response)

            # Validate entity structure
            expected_keys = ['category', 'subcategory', 'product', 'specifications',
                             'budget', 'quantity', 'order_id', 'urgency',
                             'comparison_items', 'preferences']

            for key in expected_keys:
                if key not in entities:
                    if key in ['specifications', 'comparison_items', 'preferences']:
                        entities[key] = []
                    else:
                        entities[key] = None

            return entities

        except Exception as e:
            return {
                'category': None, 'subcategory': None, 'product': None,
                'specifications': [], 'budget': None, 'quantity': None,
                'order_id': None, 'urgency': None, 'comparison_items': [],
                'preferences': []
            }

    def get_intent_confidence_threshold(self, intent: str) -> float:
        """Get confidence threshold for different intents."""
        thresholds = {
            'ORDER': 0.7,  # High confidence needed for order operations
            'PAYMENT': 0.7,  # High confidence for payment operations
            'RETURN': 0.6,  # Medium-high for returns
            'EXCHANGE': 0.6,  # Medium-high for exchanges
            'DISCOVERY': 0.5,  # Lower threshold for discovery
            'CHITCHAT': 0.4,  # Low threshold for chitchat
            'UNKNOWN': 0.0  # No threshold for unknown
        }
        return thresholds.get(intent, 0.5)

    def is_confident_prediction(self, result: Dict[str, Any]) -> bool:
        """Check if the NLU prediction meets confidence threshold."""
        current_turn = result.get('current_turn', {})
        intent = current_turn.get('intent', 'UNKNOWN')
        confidence = current_turn.get('confidence', 0.0)
        threshold = self.get_intent_confidence_threshold(intent)
        return confidence >= threshold