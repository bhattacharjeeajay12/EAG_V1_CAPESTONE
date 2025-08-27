# test_nlu.py
"""
Test cases for Enhanced NLU Module

Covers:
- Intent classification
- Entity extraction
- Continuity analysis
- Error handling
- Edge cases
"""

import pytest
import json
from unittest.mock import Mock, patch
from typing import Dict, Any

from core.nlu import EnhancedNLU, IntentStatus
chk=1

class TestEnhancedNLU:
    """Test suite for Enhanced NLU module."""

    @pytest.fixture
    def mock_llm_client(self):
        """Mock LLM client for testing."""
        mock_client = Mock()
        return mock_client

    @pytest.fixture
    def nlu(self, mock_llm_client):
        """NLU instance with mocked LLM client."""
        return EnhancedNLU(llm_client=mock_llm_client)

    @pytest.fixture
    def sample_nlu_response(self):
        """Sample valid NLU response for mocking."""
        return json.dumps({
            "current_turn": {
                "intent": "DISCOVERY",
                "sub_intent": "explore",
                "confidence": 0.85,
                "entities": {
                    "category": "electronics",
                    "subcategory": "laptops",
                    "product": None,
                    "specifications": ["gaming"],
                    "budget": "$1000-$1500",
                    "quantity": None,
                    "order_id": None,
                    "urgency": "medium",
                    "comparison_items": [],
                    "preferences": ["high performance"]
                },
                "reasoning": "User is exploring laptops with specific criteria"
            },
            "continuity": {
                "continuity_type": "CONTINUATION",
                "confidence": 0.9,
                "reasoning": "User continuing previous laptop search"
            },
            "consistency_checks": {
                "entity_conflicts_with_session": [],
                "notes": "No conflicts detected"
            }
        })

    def test_init_default_client(self):
        """Test initialization with default LLM client."""
        with patch('nlu.LLMClient') as mock_client_class:
            nlu = EnhancedNLU()
            mock_client_class.assert_called_once()
            assert nlu.valid_intents == ["DISCOVERY", "ORDER", "RETURN", "EXCHANGE", "PAYMENT", "CHITCHAT", "UNKNOWN"]

    def test_init_custom_client(self, mock_llm_client):
        """Test initialization with custom LLM client."""
        nlu = EnhancedNLU(llm_client=mock_llm_client)
        assert nlu.llm_client == mock_llm_client

    def test_analyze_message_success(self, nlu, mock_llm_client, sample_nlu_response):
        """Test successful message analysis."""
        mock_llm_client.generate.return_value = sample_nlu_response

        result = nlu.analyze_message("Show me gaming laptops under $1500")

        assert result['current_turn']['intent'] == 'DISCOVERY'
        assert result['current_turn']['sub_intent'] == 'explore'
        assert result['current_turn']['confidence'] == 0.85
        assert result['current_turn']['entities']['category'] == 'electronics'
        assert result['current_turn']['entities']['budget'] == '$1000-$1500'
        assert result['continuity']['continuity_type'] == 'CONTINUATION'

    def test_analyze_message_empty_input(self, nlu):
        """Test analysis with empty input."""
        result = nlu.analyze_message("")

        assert result['current_turn']['intent'] == 'UNKNOWN'
        assert result['current_turn']['confidence'] == 0.0
        assert 'Empty or invalid user message' in result['current_turn']['reasoning']

    def test_analyze_message_whitespace_only(self, nlu):
        """Test analysis with whitespace-only input."""
        result = nlu.analyze_message("   \n\t   ")

        assert result['current_turn']['intent'] == 'UNKNOWN'
        assert 'Empty or invalid user message' in result['current_turn']['reasoning']

    def test_analyze_message_with_context(self, nlu, mock_llm_client, sample_nlu_response):
        """Test analysis with conversation context."""
        mock_llm_client.generate.return_value = sample_nlu_response

        context = [
            {'role': 'user', 'content': 'I need a laptop'},
            {'role': 'assistant', 'content': 'What type of laptop?', 'nlu_result': {
                'current_turn': {'intent': 'DISCOVERY', 'entities': {'category': 'electronics'}}
            }},
            {'role': 'user', 'content': 'Gaming laptop under $1500'}
        ]

        result = nlu.analyze_message("Show me some options", context)

        mock_llm_client.generate.assert_called_once()
        # Verify context was used in prompt creation
        prompt_args = mock_llm_client.generate.call_args[0][0]
        assert 'Gaming laptop under $1500' in prompt_args
        assert 'DISCOVERY' in prompt_args

    def test_parse_llm_response_valid_json(self, nlu):
        """Test parsing valid JSON response."""
        json_response = '{"intent": "DISCOVERY", "confidence": 0.8}'

        result = nlu._parse_llm_response(json_response)

        assert result['intent'] == 'DISCOVERY'
        assert result['confidence'] == 0.8

    def test_parse_llm_response_markdown_wrapped(self, nlu):
        """Test parsing JSON wrapped in markdown."""
        markdown_response = '```json\n{"intent": "DISCOVERY"}\n```'

        result = nlu._parse_llm_response(markdown_response)

        assert result['intent'] == 'DISCOVERY'

    def test_parse_llm_response_invalid_json(self, nlu):
        """Test parsing invalid JSON."""
        with pytest.raises(ValueError, match="Invalid JSON response"):
            nlu._parse_llm_response('{"invalid": json}')

    def test_validate_and_clean_result_complete(self, nlu):
        """Test validation with complete valid result."""
        input_result = {
            "current_turn": {
                "intent": "discovery",  # lowercase should be converted
                "sub_intent": "explore",
                "confidence": 0.85,
                "entities": {
                    "category": "electronics",
                    "budget": "$1000",
                    "urgency": "high"
                },
                "reasoning": "User wants electronics"
            },
            "continuity": {
                "continuity_type": "CONTINUATION",
                "confidence": 0.9,
                "reasoning": "Continuing previous search"
            },
            "consistency_checks": {
                "entity_conflicts_with_session": []
            }
        }

        result = nlu._validate_and_clean_result(input_result)

        assert result['current_turn']['intent'] == 'DISCOVERY'  # Should be uppercase
        assert result['current_turn']['entities']['specifications'] == []  # Should be added
        assert result['current_turn']['entities']['category'] == 'electronics'  # Should be preserved

    def test_validate_and_clean_result_invalid_intent(self, nlu):
        """Test validation with invalid intent."""
        input_result = {
            "current_turn": {
                "intent": "INVALID_INTENT",
                "confidence": 0.85,
                "entities": {},
                "reasoning": "test"
            },
            "continuity": {"continuity_type": "CONTINUATION", "confidence": 0.9, "reasoning": "test"},
            "consistency_checks": {"entity_conflicts_with_session": []}
        }

        result = nlu._validate_and_clean_result(input_result)

        assert result['current_turn']['intent'] == 'UNKNOWN'

    def test_validate_and_clean_result_invalid_confidence(self, nlu):
        """Test validation with invalid confidence values."""
        input_result = {
            "current_turn": {
                "intent": "DISCOVERY",
                "confidence": 1.5,  # Invalid - over 1.0
                "entities": {},
                "reasoning": "test"
            },
            "continuity": {"continuity_type": "CONTINUATION", "confidence": -0.1, "reasoning": "test"},
            # Invalid - negative
            "consistency_checks": {"entity_conflicts_with_session": []}
        }

        result = nlu._validate_and_clean_result(input_result)

        assert result['current_turn']['confidence'] == 0.5  # Should be clamped
        assert result['continuity']['confidence'] == 0.5  # Should be clamped

    def test_validate_and_clean_result_context_switch(self, nlu):
        """Test validation with context switch continuity."""
        input_result = {
            "current_turn": {
                "intent": "DISCOVERY",
                "confidence": 0.8,
                "entities": {},
                "reasoning": "test"
            },
            "continuity": {
                "continuity_type": "CONTEXT_SWITCH",
                "confidence": 0.9,
                "reasoning": "test",
                "context_switch_options": ["REPLACE", "INVALID_OPTION"]
            },
            "consistency_checks": {"entity_conflicts_with_session": []}
        }

        result = nlu._validate_and_clean_result(input_result)

        assert result['continuity']['continuity_type'] == 'CONTEXT_SWITCH'
        assert result['continuity']['context_switch_options'] == ['REPLACE']  # Invalid option removed

    def test_validate_and_clean_result_unclear_continuity(self, nlu):
        """Test validation with unclear continuity."""
        input_result = {
            "current_turn": {
                "intent": "DISCOVERY",
                "confidence": 0.8,
                "entities": {},
                "reasoning": "test"
            },
            "continuity": {
                "continuity_type": "UNCLEAR",
                "confidence": 0.3,
                "reasoning": "test"
            },
            "consistency_checks": {"entity_conflicts_with_session": []}
        }

        result = nlu._validate_and_clean_result(input_result)

        assert result['continuity']['continuity_type'] == 'UNCLEAR'
        assert 'suggested_clarification' in result['continuity']

    def test_create_error_response(self, nlu):
        """Test error response creation."""
        error_msg = "Test error message"

        result = nlu._create_error_response(error_msg)

        assert result['current_turn']['intent'] == 'UNKNOWN'
        assert result['current_turn']['confidence'] == 0.0
        assert error_msg in result['current_turn']['reasoning']
        assert result['continuity']['continuity_type'] == 'UNCLEAR'
        assert 'suggested_clarification' in result['continuity']

    def test_extract_entities_only_success(self, nlu, mock_llm_client):
        """Test entity-only extraction."""
        mock_response = json.dumps({
            "category": "electronics",
            "subcategory": "smartphones",
            "budget": "$500",
            "specifications": ["Android"],
            "comparison_items": [],
            "preferences": []
        })
        mock_llm_client.generate.return_value = mock_response

        entities = nlu.extract_entities_only("I want an Android phone under $500")

        assert entities['category'] == 'electronics'
        assert entities['subcategory'] == 'smartphones'
        assert entities['budget'] == '$500'
        assert entities['specifications'] == ['Android']

    def test_extract_entities_only_error(self, nlu, mock_llm_client):
        """Test entity extraction with error."""
        mock_llm_client.generate.side_effect = Exception("LLM error")

        entities = nlu.extract_entities_only("test message")

        # Should return default empty entities structure
        assert entities['category'] is None
        assert entities['specifications'] == []

    def test_get_intent_confidence_threshold(self, nlu):
        """Test confidence threshold retrieval."""
        assert nlu.get_intent_confidence_threshold('ORDER') == 0.7
        assert nlu.get_intent_confidence_threshold('DISCOVERY') == 0.5
        assert nlu.get_intent_confidence_threshold('UNKNOWN_INTENT') == 0.5  # default

    def test_is_confident_prediction_high_confidence(self, nlu):
        """Test confidence check with high confidence."""
        result = {
            'current_turn': {
                'intent': 'ORDER',
                'confidence': 0.8
            }
        }

        assert nlu.is_confident_prediction(result) is True

    def test_is_confident_prediction_low_confidence(self, nlu):
        """Test confidence check with low confidence."""
        result = {
            'current_turn': {
                'intent': 'ORDER',
                'confidence': 0.5  # Below ORDER threshold of 0.7
            }
        }

        assert nlu.is_confident_prediction(result) is False

    def test_analyze_message_llm_error(self, nlu, mock_llm_client):
        """Test analysis when LLM client throws error."""
        mock_llm_client.generate.side_effect = Exception("LLM connection error")

        result = nlu.analyze_message("test message")

        assert result['current_turn']['intent'] == 'UNKNOWN'
        assert result['current_turn']['confidence'] == 0.0
        assert 'NLU analysis failed' in result['current_turn']['reasoning']

    def test_create_nlu_prompt_no_context(self, nlu):
        """Test prompt creation with no context."""
        with patch('nlu_prompt.COMBINED_SYSTEM_PROMPT', 'Test prompt: {current_message}'):
            prompt = nlu._create_nlu_prompt("Hello", [])
            assert "Hello" in prompt

    def test_create_nlu_prompt_with_context(self, nlu):
        """Test prompt creation with conversation context."""
        context = [
            {'role': 'user', 'content': 'I need a laptop'},
            {'role': 'assistant', 'content': 'What type?', 'nlu_result': {
                'current_turn': {'intent': 'DISCOVERY', 'entities': {'category': 'electronics'}}
            }}
        ]

        with patch('nlu_prompt.COMBINED_SYSTEM_PROMPT',
                   'Current: {current_message}, Last intent: {last_intent}, Session: {session_entities_json}'):
            prompt = nlu._create_nlu_prompt("Gaming laptop", context)
            assert "Gaming laptop" in prompt
            assert "DISCOVERY" in prompt
            assert "electronics" in prompt


class TestIntegrationScenarios:
    """Integration tests with realistic e-commerce scenarios."""

    @pytest.fixture
    def nlu_with_real_responses(self):
        """NLU with mocked but realistic responses."""
        mock_client = Mock()
        nlu = EnhancedNLU(llm_client=mock_client)
        return nlu, mock_client

    def test_discovery_scenario(self, nlu_with_real_responses):
        """Test complete discovery conversation flow."""
        nlu, mock_client = nlu_with_real_responses

        # Mock response for "I need a laptop"
        mock_client.generate.return_value = json.dumps({
            "current_turn": {
                "intent": "DISCOVERY",
                "sub_intent": "explore",
                "confidence": 0.9,
                "entities": {
                    "category": "electronics",
                    "subcategory": "laptops",
                    "product": None,
                    "specifications": [],
                    "budget": None,
                    "quantity": None,
                    "order_id": None,
                    "urgency": None,
                    "comparison_items": [],
                    "preferences": []
                },
                "reasoning": "User is exploring laptops"
            },
            "continuity": {
                "continuity_type": "CONTINUATION",
                "confidence": 0.8,
                "reasoning": "Starting new laptop search"
            },
            "consistency_checks": {
                "entity_conflicts_with_session": []
            }
        })

        result = nlu.analyze_message("I need a laptop")

        assert result['current_turn']['intent'] == 'DISCOVERY'
        assert result['current_turn']['entities']['category'] == 'electronics'
        assert result['current_turn']['entities']['subcategory'] == 'laptops'

    def test_order_tracking_scenario(self, nlu_with_real_responses):
        """Test order tracking scenario."""
        nlu, mock_client = nlu_with_real_responses

        mock_client.generate.return_value = json.dumps({
            "current_turn": {
                "intent": "ORDER",
                "sub_intent": "track",
                "confidence": 0.95,
                "entities": {
                    "category": None,
                    "subcategory": None,
                    "product": None,
                    "specifications": [],
                    "budget": None,
                    "quantity": None,
                    "order_id": "ORD123456",
                    "urgency": "high",
                    "comparison_items": [],
                    "preferences": []
                },
                "reasoning": "User wants to track specific order"
            },
            "continuity": {
                "continuity_type": "INTENT_SWITCH",
                "confidence": 0.9,
                "reasoning": "Switching from discovery to order tracking"
            },
            "consistency_checks": {
                "entity_conflicts_with_session": []
            }
        })

        result = nlu.analyze_message("Where is my order ORD123456?")

        assert result['current_turn']['intent'] == 'ORDER'
        assert result['current_turn']['sub_intent'] == 'track'
        assert result['current_turn']['entities']['order_id'] == 'ORD123456'
        assert result['continuity']['continuity_type'] == 'INTENT_SWITCH'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])