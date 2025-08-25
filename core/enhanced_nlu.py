# core/enhanced_nlu.py
"""
Enhanced Natural Language Understanding Module

Purpose: Focused on pure language understanding - extracting intent and entities
from user messages without making conversation flow decisions. This module
provides clean, structured output for the Planner to make routing decisions.

Key Responsibilities:
- Intent classification (BUY, ORDER, RECOMMEND, RETURN)
- Entity extraction (category, subcategory, budget, order_id, etc.)
- Confidence scoring
- Clean, structured output format

Does NOT handle:
- Intent continuity analysis (Intent Tracker's job)
- Conversation flow decisions (Planner's job)
- Context management (Context Manager's job)
"""

# Load environment variables from .env file
from dotenv import load_dotenv
load_dotenv()


import json
from typing import Dict, List, Optional, Any
from core.llm_client import LLMClient


class EnhancedNLU:
    """
    Pure NLU module focused on understanding user messages.

    This module analyzes user input and returns structured information
    about what the user wants (intent) and relevant details (entities).
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
        self.valid_intents = ["BUY", "ORDER", "RECOMMEND", "RETURN"]

    def analyze_message(self, user_message: str, conversation_context: List[Dict] = None) -> Dict[str, Any]:
        """
        Analyze user message and extract intent and entities.

        Args:
            user_message: The user's input message
            conversation_context: Recent conversation history for context

        Returns:
            Dictionary with intent, entities, confidence, and reasoning
        """
        if not user_message or not user_message.strip():
            return self._create_error_response("Empty or invalid user message")

        try:
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
        """
        Create focused NLU prompt for intent and entity extraction.

        Args:
            user_message: User's current message
            conversation_context: Recent conversation history

        Returns:
            Complete prompt for LLM
        """
        # Format conversation context
        context_str = self._format_conversation_context(conversation_context)

        prompt = f"""
You are an expert NLU system for an e-commerce platform. Your job is to analyze user messages and extract structured information.

AVAILABLE INTENTS:
- BUY: User wants to search for or purchase products
- ORDER: User wants to check, modify, or track existing orders  
- RECOMMEND: User wants product suggestions or comparisons
- RETURN: User wants to return, exchange, or get refunds

ENTITY TYPES TO EXTRACT:
- category: electronics, books, sports, clothing, etc.
- subcategory: laptop, smartphone, cricket bat, yoga mat, etc.
- product: specific product mentions with brands
- specifications: product attributes (brand, color, size, etc.)
- budget: price ranges or maximum budget
- quantity: how many items needed
- order_id: order reference numbers
- return_reason: why user wants to return
- preferences: user's stated preferences or requirements

CONVERSATION CONTEXT:
{context_str}

CURRENT USER MESSAGE:
"{user_message}"

Analyze ONLY the current message and return structured JSON:

{{
  "intent": "BUY|ORDER|RECOMMEND|RETURN",
  "confidence": 0.0-1.0,
  "entities": {{
    "category": "value_or_null",
    "subcategory": "value_or_null", 
    "product": "value_or_null",
    "specifications": ["list_or_empty"],
    "budget": "value_or_null",
    "quantity": "number_or_null",
    "order_id": "value_or_null",
    "return_reason": "value_or_null",
    "preferences": ["list_or_empty"]
  }},
  "reasoning": "brief_explanation_of_classification"
}}

Focus on understanding what the user wants RIGHT NOW, not conversation flow.
"""
        return prompt

    def _format_conversation_context(self, context: List[Dict]) -> str:
        """Format conversation context for LLM prompt."""
        if not context:
            return "No previous conversation"

        # Take last 3 exchanges to avoid token limits
        recent_context = context[-6:]

        formatted = []
        for entry in recent_context:
            role = entry.get('role', 'unknown')
            content = entry.get('content', '')
            formatted.append(f"{role}: {content}")

        return "\n".join(formatted) if formatted else "No previous conversation"

    def _parse_llm_response(self, llm_response: str) -> Dict[str, Any]:
        """
        Parse LLM response into structured data.

        Args:
            llm_response: Raw response from LLM

        Returns:
            Parsed NLU result dictionary
        """
        # Handle fallback responses
        if llm_response.startswith("[LLM-FALLBACK]"):
            return self._handle_fallback_response(llm_response)

        try:
            # Clean the response - remove markdown formatting
            response = llm_response.strip()

            # Remove code block markers if present
            if response.startswith('```json'):
                response = response[7:]
            elif response.startswith('```'):
                response = response[3:]

            if response.endswith('```'):
                response = response[:-3]

            response = response.strip()

            # Extract JSON from response
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
        Handle LLM fallback with basic pattern matching.

        Args:
            fallback_response: Fallback response from LLM client

        Returns:
            Basic NLU result based on simple patterns
        """
        # Extract user message from fallback for pattern matching
        user_message = ""
        if "CURRENT USER MESSAGE:" in fallback_response:
            lines = fallback_response.split("\n")
            for line in lines:
                if "CURRENT USER MESSAGE:" in line:
                    user_message = line.split('"')[1] if '"' in line else ""
                    break

        message_lower = user_message.lower()

        # Simple pattern-based classification
        if any(word in message_lower for word in ["track", "order", "status", "delivery"]):
            return self._create_fallback_result("ORDER", ["order_id"])
        elif any(word in message_lower for word in ["return", "refund", "exchange"]):
            return self._create_fallback_result("RETURN", ["order_id"])
        elif any(word in message_lower for word in ["recommend", "suggest", "best", "compare"]):
            return self._create_fallback_result("RECOMMEND", ["category"])
        else:
            return self._create_fallback_result("BUY", ["category"])

    def _create_fallback_result(self, intent: str, missing_entities: List[str]) -> Dict[str, Any]:
        """Create fallback NLU result."""
        return {
            "intent": intent,
            "confidence": 0.6,
            "entities": {
                "category": None,
                "subcategory": None,
                "product": None,
                "specifications": [],
                "budget": None,
                "quantity": None,
                "order_id": None,
                "return_reason": None,
                "preferences": []
            },
            "reasoning": f"Fallback classification as {intent} based on keywords"
        }

    def _validate_and_clean_result(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate and clean the NLU result.

        Args:
            result: Raw result from LLM parsing

        Returns:
            Validated and cleaned result
        """
        validated = {}

        # Validate intent
        intent = result.get("intent", "BUY")
        validated["intent"] = intent if intent in self.valid_intents else "BUY"

        # Validate confidence
        confidence = result.get("confidence", 0.5)
        try:
            validated["confidence"] = max(0.0, min(1.0, float(confidence)))
        except (ValueError, TypeError):
            validated["confidence"] = 0.5

        # Validate entities with proper structure
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
            "return_reason": entities.get("return_reason"),
            "preferences": entities.get("preferences", []) if isinstance(entities.get("preferences"), list) else []
        }

        # Validate reasoning
        validated["reasoning"] = result.get("reasoning", "NLU analysis completed")

        # Add analysis metadata
        validated["analysis_metadata"] = {
            "timestamp": self._get_current_timestamp(),
            "nlu_version": "enhanced_v1.0"
        }

        return validated

    def _create_error_response(self, error_message: str) -> Dict[str, Any]:
        """
        Create standardized error response.

        Args:
            error_message: Description of the error

        Returns:
            Error response in standard NLU format
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
                "return_reason": None,
                "preferences": []
            },
            "reasoning": f"Error: {error_message}",
            "analysis_metadata": {
                "timestamp": self._get_current_timestamp(),
                "nlu_version": "enhanced_v1.0",
                "error": True
            }
        }

    def _get_current_timestamp(self) -> str:
        """Get current timestamp in ISO format."""
        from datetime import datetime
        return datetime.now().isoformat()


def test_enhanced_nlu():
    """Test the Enhanced NLU module with various scenarios."""
    print("🧪 Testing Enhanced NLU Module")
    print("=" * 50)

    # Initialize NLU
    nlu = EnhancedNLU()

    # Test cases covering different intents and complexity
    test_cases = [
        {
            "name": "Simple BUY intent",
            "message": "I want to buy a laptop",
            "context": []
        },
        {
            "name": "BUY with specific details",
            "message": "Show me gaming laptops under $1500 with RTX graphics",
            "context": []
        },
        {
            "name": "ORDER tracking",
            "message": "Where is my order #12345?",
            "context": []
        },
        {
            "name": "RECOMMEND request",
            "message": "What's the best smartphone for photography?",
            "context": []
        },
        {
            "name": "RETURN with reason",
            "message": "I want to return my defective headphones from order ABC123",
            "context": []
        },
        {
            "name": "Intent with conversation context",
            "message": "Actually, make it under $1000",
            "context": [
                {"role": "user", "content": "I want to buy a laptop"},
                {"role": "system", "content": "What's your budget?"}
            ]
        }
    ]

    print(f"🔍 Running {len(test_cases)} test cases:\n")

    for i, test_case in enumerate(test_cases, 1):
        print(f"Test {i}: {test_case['name']}")
        print(f"  Message: '{test_case['message']}'")

        # Analyze message
        result = nlu.analyze_message(test_case['message'], test_case['context'])

        print(f"  Intent: {result['intent']} (confidence: {result['confidence']:.2f})")

        # Show non-null entities
        entities = result['entities']
        non_null_entities = {k: v for k, v in entities.items() if v is not None and v != []}
        if non_null_entities:
            print(f"  Entities: {non_null_entities}")

        print(f"  Reasoning: {result['reasoning']}")

        # Check for errors
        if result.get('analysis_metadata', {}).get('error'):
            print(f"  ⚠️  Error occurred during analysis")

        print()  # Empty line for readability

    # Test error handling
    print("🚨 Testing Error Handling:")
    error_result = nlu.analyze_message("")
    print(f"  Empty message result: {error_result['reasoning']}")

    # Test validation
    print("\n✅ Testing Result Validation:")
    print(
        f"  All intents valid: {all(result['intent'] in nlu.valid_intents for result in [nlu.analyze_message(tc['message']) for tc in test_cases])}")
    print(
        f"  All confidences in range: {all(0 <= result['confidence'] <= 1 for result in [nlu.analyze_message(tc['message']) for tc in test_cases])}")

    print("\n" + "=" * 50)
    print("✅ Enhanced NLU Tests Complete!")


if __name__ == "__main__":
    test_enhanced_nlu()