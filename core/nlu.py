# nlu/nlu_prompt.py
"""
Natural Language Understanding Module for E-commerce System
Uses LLM client for intent classification and entity extraction.
"""

import json
from typing import Dict, List, Optional, Any
from core.llm_client import LLMClient
from prompts.nlu_prompt import NLU_SYSTEM_PROMPT, NLU_USER_PROMPT_TEMPLATE


class NLUModule:
    """
    Natural Language Understanding module that uses LLM for all processing.

    This module:
    1. Takes user messages and optional chat history
    2. Uses LLM to classify intent and extract entities
    3. Returns structured JSON for the Planner Agent
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize the NLU module.

        Args:
            llm_client (LLMClient, optional): LLM client instance. If None, creates a new one.
        """
        self.llm_client = llm_client or LLMClient()
        self.valid_intents = ["BUY", "ORDER", "RECOMMEND", "RETURN"]

    def analyze(self, user_message: str, chat_history: Optional[List[Dict]] = None) -> Dict[str, Any]:
        """
        Analyze user input using LLM and return structured NLU results.

        Args:
            user_message (str): The user's message to analyze
            chat_history (List[Dict], optional): Previous conversation context

        Returns:
            Dict containing intent, entities, confidence, and other NLU results
        """
        if not user_message or not user_message.strip():
            return self._create_error_response("Empty or invalid user message")

        try:
            # Format chat history for context
            history_str = self._format_chat_history(chat_history or [])

            # Create the complete prompt
            full_prompt = self._create_llm_prompt(user_message.strip(), history_str)

            # Call LLM for analysis
            llm_response = self.llm_client.generate(full_prompt)

            # Parse and validate the LLM response
            result = self._parse_llm_response(llm_response)
            return self._validate_result(result)

        except Exception as e:
            return self._create_error_response(f"Analysis failed: {str(e)}")

    def _create_llm_prompt(self, user_message: str, chat_history: str) -> str:
        """
        Create the complete prompt for LLM including system instructions and user input.

        Args:
            user_message (str): User's message
            chat_history (str): Formatted chat history

        Returns:
            str: Complete prompt for LLM
        """
        user_prompt = NLU_USER_PROMPT_TEMPLATE.format(
            user_message=user_message,
            chat_history=chat_history
        )

        # Combine system prompt and user prompt
        full_prompt = f"{NLU_SYSTEM_PROMPT}\n\n{user_prompt}"
        return full_prompt

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse the LLM response into structured data.

        Args:
            llm_response (str): Raw LLM response

        Returns:
            Dict: Parsed NLU result
        """
        # Handle fallback responses
        if llm_response.startswith("[LLM-FALLBACK]"):
            return self._handle_fallback_response(llm_response)

        try:
            # Clean the response - remove markdown formatting if present
            response = llm_response.strip()

            if response.startswith('```json'):
                response = response[7:]
            elif response.startswith('```'):
                response = response[3:]

            if response.endswith('```'):
                response = response[:-3]

            response = response.strip()

            # Find JSON in the response
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in LLM response")

            json_str = response[json_start:json_end]
            result = json.loads(json_str)

            return result

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse LLM JSON response: {str(e)}")
        except Exception as e:
            raise Exception(f"Failed to process LLM response: {str(e)}")

    def _handle_fallback_response(self, fallback_response: str) -> Dict[str, Any]:
        """
        Handle LLM fallback responses with basic pattern matching.

        Args:
            fallback_response (str): Fallback response from LLM client

        Returns:
            Dict: Basic NLU result based on patterns
        """
        # Extract the original prompt from fallback
        prompt_part = fallback_response.replace("[LLM-FALLBACK]", "").strip()

        # Extract user message for pattern matching
        user_message = ""
        if "User Message:" in prompt_part:
            lines = prompt_part.split("\n")
            for line in lines:
                if "User Message:" in line:
                    user_message = line.split("User Message:")[1].strip().strip('"')
                    break

        message_lower = user_message.lower()

        # Basic pattern-based classification
        if any(word in message_lower for word in ["track", "order", "where", "status", "delivery"]):
            return {
                "intent": "ORDER",
                "confidence": 0.7,
                "entities": {
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
                },
                "clarification_needed": ["order_id"],
                "reasoning": "Order-related keywords detected (fallback mode)"
            }

        elif any(word in message_lower for word in ["return", "refund", "exchange", "defective"]):
            return {
                "intent": "RETURN",
                "confidence": 0.7,
                "entities": {
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
                },
                "clarification_needed": ["order_id"],
                "reasoning": "Return-related keywords detected (fallback mode)"
            }

        elif any(word in message_lower for word in ["recommend", "suggest", "best", "compare", "advice"]):
            return {
                "intent": "RECOMMEND",
                "confidence": 0.7,
                "entities": {
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
                },
                "clarification_needed": ["category"],
                "reasoning": "Recommendation keywords detected (fallback mode)"
            }

        else:
            # Default to BUY intent
            return {
                "intent": "BUY",
                "confidence": 0.6,
                "entities": {
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
                },
                "clarification_needed": ["category", "subcategory"],
                "reasoning": "Default to purchase intent (fallback mode)"
            }

    def _validate_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean the NLU result.

        Args:
            result (Dict): Raw result from LLM

        Returns:
            Dict: Validated and cleaned result
        """
        validated = {}

        # Validate intent
        # Validate intent
        intent = result.get("intent", "BUY")
        validated["intent"] = intent if intent in self.valid_intents else "BUY"

        # Validate confidence
        confidence = result.get("confidence", 0.5)
        try:
            validated["confidence"] = max(0.0, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            validated["confidence"] = 0.5

        # Validate entities
        entities = result.get("entities", {})
        validated["entities"] = {
            "category": entities.get("category"),
            "subcategory": entities.get("subcategory"),
            "product": entities.get("product"),
            "specifications": entities.get("specifications", []) if isinstance(entities.get("specifications"),
                                                                               list) else [],
            "budget": entities.get("budget"),
            "quantity": entities.get("quantity"),
            "order_id": entities.get("order_id"),
            "urgency": entities.get("urgency"),
            "comparison_items": entities.get("comparison_items", []) if isinstance(entities.get("comparison_items"),
                                                                                   list) else [],
            "preferences": entities.get("preferences", []) if isinstance(entities.get("preferences"), list) else []
        }

        # Validate other fields
        validated["clarification_needed"] = result.get("clarification_needed", []) if isinstance(result.get("clarification_needed"), list) else []
        validated["reasoning"] = result.get("reasoning", "LLM analysis completed")

        return validated

    def _format_chat_history(self, chat_history: List[Dict]) -> str:
        """
        Format chat history for LLM context.

        Args:
            chat_history (List[Dict]): Chat history entries

        Returns:
            str: Formatted chat history
        """
        if not chat_history:
            return "No previous conversation"

        # Take only the last 3 exchanges to avoid token limits
        recent_history = chat_history[-6:]  # Last 3 user-agent exchanges

        formatted = []
        for entry in recent_history:
            role = entry.get('role', 'user')
            content = entry.get('content', '')
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted) if formatted else "No previous conversation"

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        Create a standardized error response.

        Args:
            error_message (str): Error description

        Returns:
            Dict: Error response in standard format
        """
        return {
            "intent": "BUY",
            "confidence": 0.0,
            "entities": {
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
            },
            "clarification_needed": ["valid_user_input"],
            "reasoning": f"Error: {error_message}"
        }


def test_nlu_module():
    """
    Test the NLU module with various examples.
    Works with both real LLM and fallback mode.
    """
    print("🧪 Testing NLU Module with LLM Client")
    print("=" * 50)

    # Initialize NLU with LLM client
    nlu = NLUModule()

    test_cases = [
        "I want to buy a MacBook Pro under $2000",
        "Track my order #12345",
        "What's the best smartphone for photography?",
        "I need to return my defective laptop",
        "Show me gaming laptops with RTX 4080",
        "Where is my delivery? It's urgent",
        "Compare iPhone 15 and Samsung Galaxy S24"
    ]

    for i, message in enumerate(test_cases, 1):
        print(f"\n🔍 Test {i}: {message}")
        result = nlu.analyze(message)

        print(f"   Intent: {result['intent']}")
        print(f"   Confidence: {result['confidence']}")

        # Show non-null entities
        entities = result['entities']
        if entities.get('category'):
            print(f"   Category: {entities['category']}")
        if entities.get('subcategory'):
            print(f"   Subcategory: {entities['subcategory']}")
        if entities.get('product'):
            print(f"   Product: {entities['product']}")
        if entities.get('budget'):
            print(f"   Budget: {entities['budget']}")
        if entities.get('specifications'):
            print(f"   Specifications: {entities['specifications']}")

        if result['clarification_needed']:
            print(f"   Clarifications needed: {result['clarification_needed']}")

        print(f"   Reasoning: {result['reasoning']}")

    print("\n" + "=" * 50)
    print("✅ NLU Module Testing Complete!")


if __name__ == "__main__":
    test_nlu_module()

    # Example usage
    print("\n" + "=" * 50)
    print("📝 Example Usage:")

    nlu = NLUModule()
    example_message = "I want to buy Nike running shoes under $150"
    result = nlu.analyze(example_message)

    print(f"Input: {example_message}")
    print("Output:")
    print(json.dumps(result, indent=2))