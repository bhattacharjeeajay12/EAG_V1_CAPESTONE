# core/intent_tracker.py
"""
Intent Tracker with LLM-Powered Continuity Analysis

Purpose: Tracks user intents throughout the conversation and uses LLM intelligence
to determine if new user messages represent intent continuation, switching, or addition.
Handles two types of switches: INTENT_SWITCH (different intent types) and
CONTEXT_SWITCH (same intent, different target/subject).

Key Responsibilities:
- Track active, suspended, and completed intents
- LLM-powered intent continuity analysis (CONTINUATION/INTENT_SWITCH/CONTEXT_SWITCH/ADDITION/UNCLEAR)
- ALWAYS require clarification for any type of switch
- Generate appropriate clarification questions for each switch type

Switch Types:
- INTENT_SWITCH: Different intent types (BUY → RETURN, ORDER → RECOMMEND)
- CONTEXT_SWITCH: Same intent, different target (Buy laptop → Buy cupboard, Return order1 → Return order2)
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
from datetime import datetime
from core.llm_client import LLMClient


class IntentStatus(Enum):
    """Status of tracked intents."""
    ACTIVE = "active"  # Currently being worked on
    SUSPENDED = "suspended"  # Temporarily paused
    COMPLETED = "completed"  # Successfully finished
    ABANDONED = "abandoned"  # User cancelled/switched away


class ContinuityType(Enum):
    """Types of intent continuity relationships."""
    CONTINUATION = "continuation"  # Same intent, refinement/clarification
    INTENT_SWITCH = "intent_switch"  # Different intent types (BUY → RETURN)
    CONTEXT_SWITCH = "context_switch"  # Same intent, different target (Buy laptop → Buy cupboard)
    ADDITION = "addition"  # New intent while keeping previous
    UNCLEAR = "unclear"  # Ambiguous, needs user clarification


@dataclass
class TrackedIntent:
    """Represents a user intent being tracked through conversation."""

    intent_type: str  # BUY, ORDER, RECOMMEND, RETURN
    entities: Dict[str, Any]  # Extracted entities
    status: IntentStatus = IntentStatus.ACTIVE
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    context_data: Dict[str, Any] = field(default_factory=dict)

    def get_summary(self) -> str:
        """Get human-readable summary of this intent."""
        entity_summary = []
        if self.entities.get('category'):
            entity_summary.append(f"category: {self.entities['category']}")
        if self.entities.get('product'):
            entity_summary.append(f"product: {self.entities['product']}")
        if self.entities.get('subcategory'):
            entity_summary.append(f"subcategory: {self.entities['subcategory']}")
        if self.entities.get('order_id'):
            entity_summary.append(f"order: {self.entities['order_id']}")

        entity_str = f" ({', '.join(entity_summary)})" if entity_summary else ""
        return f"{self.intent_type}{entity_str}"


@dataclass
class ContinuityAnalysis:
    """Result of intent continuity analysis."""

    continuity_type: ContinuityType
    confidence: float
    reasoning: str
    requires_clarification: bool = False
    suggested_clarification: Optional[str] = None
    recommended_action: str = "continue"  # continue, clarify, switch, add


class IntentTracker:
    """
    Manages intent tracking with LLM-powered continuity analysis.

    This class maintains conversation state and uses LLM intelligence to
    determine how new user messages relate to previous intents. It enforces
    that ANY type of switch (intent or context) requires user clarification.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """
        Initialize Intent Tracker.

        Args:
            llm_client: LLM client for continuity analysis. If None, creates default.
        """
        self.llm_client = llm_client or LLMClient()
        self.tracked_intents: List[TrackedIntent] = []
        self.current_intent_index: Optional[int] = None

    def analyze_intent_continuity(self, previous_intent: TrackedIntent,
                                  new_nlu_result: Dict[str, Any],
                                  conversation_context: List[Dict]) -> ContinuityAnalysis:
        """
        Use LLM to analyze how new user message relates to previous intent.
        Enforces that both INTENT_SWITCH and CONTEXT_SWITCH require clarification.

        Args:
            previous_intent: The currently active intent
            new_nlu_result: NLU analysis of new user message
            conversation_context: Recent conversation messages

        Returns:
            ContinuityAnalysis with relationship type and mandatory clarification for switches
        """
        try:
            # Create LLM prompt for continuity analysis
            prompt = self._create_continuity_prompt(previous_intent, new_nlu_result, conversation_context)

            # Get LLM analysis
            llm_response = self.llm_client.generate(prompt)

            # Parse response
            analysis = self._parse_continuity_response(llm_response)

            # Enforce clarification policy for switches
            analysis = self._enforce_clarification_policy(analysis, previous_intent, new_nlu_result)

            return analysis

        except Exception as e:
            # Fallback to rule-based analysis on error
            return self._fallback_continuity_analysis(previous_intent, new_nlu_result, str(e))

    def track_new_intent(self, nlu_result: Dict[str, Any],
                         conversation_context: List[Dict]) -> Dict[str, Any]:
        """
        Process new NLU result and determine appropriate action.

        Args:
            nlu_result: Result from NLU analysis
            conversation_context: Recent conversation history

        Returns:
            Dictionary with tracking result and recommended action
        """
        new_intent_type = nlu_result["intent"]
        new_entities = nlu_result.get("entities", {})
        confidence = nlu_result.get("confidence", 0.5)

        # If no previous intent, start tracking this one
        if not self.tracked_intents or self.current_intent_index is None:
            return self._start_new_intent(new_intent_type, new_entities, confidence)

        # Get current active intent
        current_intent = self.tracked_intents[self.current_intent_index]

        # Analyze continuity with previous intent
        continuity_analysis = self.analyze_intent_continuity(
            current_intent, nlu_result, conversation_context
        )

        # Process based on continuity type
        return self._process_continuity_result(
            continuity_analysis, new_intent_type, new_entities, confidence
        )

    def get_current_intent(self) -> Optional[TrackedIntent]:
        """Get currently active intent."""
        if self.current_intent_index is not None and self.current_intent_index < len(self.tracked_intents):
            return self.tracked_intents[self.current_intent_index]
        return None

    def complete_current_intent(self) -> Optional[TrackedIntent]:
        """
        Mark current intent as completed and activate any suspended intents.

        Returns:
            Next active intent if any, None otherwise
        """
        current = self.get_current_intent()
        if current:
            current.status = IntentStatus.COMPLETED

            # Look for suspended intents to reactivate
            for i, intent in enumerate(self.tracked_intents):
                if intent.status == IntentStatus.SUSPENDED:
                    intent.status = IntentStatus.ACTIVE
                    self.current_intent_index = i
                    return intent

            # No suspended intents
            self.current_intent_index = None

        return None

    def resolve_clarification(self, user_response: str, pending_analysis: ContinuityAnalysis,
                              new_intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Resolve user clarification about intent continuity.

        Args:
            user_response: User's clarification response
            pending_analysis: The analysis that required clarification
            new_intent_data: Data for the new/conflicting intent

        Returns:
            Resolution result with action to take
        """
        response_lower = user_response.lower()

        # Parse user choice
        if any(word in response_lower for word in ["continue", "same", "current", "keep"]):
            return self._resolve_continue_current()

        elif any(word in response_lower for word in ["switch", "new", "change", "different"]):
            return self._resolve_switch_intent(new_intent_data)

        elif any(word in response_lower for word in ["both", "add", "also", "too"]):
            return self._resolve_add_intent(new_intent_data)

        else:
            # Unclear response - ask again with simpler options
            return {
                "action": "re_clarify",
                "message": "I didn't understand. Please say: 'continue current', 'switch to new', or 'do both'",
                "requires_clarification": True
            }

    def _create_continuity_prompt(self, previous_intent: TrackedIntent,
                                  new_nlu_result: Dict[str, Any],
                                  conversation_context: List[Dict]) -> str:
        """Create LLM prompt for intent continuity analysis with switch detection."""

        # Format conversation context
        context_str = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in conversation_context[-4:]  # Last 4 messages
        ]) if conversation_context else "No previous conversation"

        prompt = f"""
You are an expert conversation analyst. Analyze how a new user message relates to their previous intent.

PREVIOUS INTENT:
- Type: {previous_intent.intent_type}
- Details: {previous_intent.get_summary()}
- Status: {previous_intent.status.value}

NEW MESSAGE ANALYSIS:
- Intent: {new_nlu_result['intent']}
- Entities: {new_nlu_result.get('entities', {})}
- Confidence: {new_nlu_result.get('confidence', 0.5)}

RECENT CONVERSATION:
{context_str}

ANALYSIS TASK:
Determine the relationship between the previous intent and new message:

1. CONTINUATION - Same goal, just refining/clarifying (e.g., "laptop" → "gaming laptop under $1000")

2. INTENT_SWITCH - Different intent types (e.g., "buy laptop" → "return phone", "track order" → "get recommendations")

3. CONTEXT_SWITCH - Same intent type but different target/subject (e.g., "buy laptop" → "buy cupboard", "return order A" → "return order B")

4. ADDITION - New goal while keeping previous (e.g., "buy laptop" → "also check return policy")

5. UNCLEAR - Ambiguous, needs clarification

IMPORTANT: 
- Focus on intent types AND the subject/target of the intent
- If user switches from one product to another product (even same intent), that's CONTEXT_SWITCH
- If user switches from one order to another order (even same intent), that's CONTEXT_SWITCH

Return JSON:
{{
  "continuity_type": "CONTINUATION|INTENT_SWITCH|CONTEXT_SWITCH|ADDITION|UNCLEAR",
  "confidence": 0.0-1.0,
  "reasoning": "detailed_explanation_of_analysis",
  "suggested_clarification": "question_to_ask_user_or_null"
}}

Be precise in detecting both intent changes AND target/subject changes.
"""
        return prompt

    def _parse_continuity_response(self, llm_response: str) -> ContinuityAnalysis:
        """Parse LLM response into ContinuityAnalysis object."""

        # Handle fallback responses
        if llm_response.startswith("[LLM-FALLBACK]"):
            return self._create_fallback_analysis("LLM fallback mode")

        try:
            # Clean and parse JSON
            response = llm_response.strip()
            if response.startswith('```json'):
                response = response[7:]
            elif response.startswith('```'):
                response = response[3:]
            if response.endswith('```'):
                response = response[:-3]

            response = response.strip()

            # Extract JSON
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")

            json_str = response[json_start:json_end]
            parsed = json.loads(json_str)

            # Create ContinuityAnalysis object
            continuity_type_str = parsed.get("continuity_type", "UNCLEAR")
            try:
                continuity_type = ContinuityType(continuity_type_str.lower())
            except ValueError:
                continuity_type = ContinuityType.UNCLEAR

            return ContinuityAnalysis(
                continuity_type=continuity_type,
                confidence=max(0.0, min(1.0, float(parsed.get("confidence", 0.5)))),
                reasoning=parsed.get("reasoning", "LLM analysis completed"),
                suggested_clarification=parsed.get("suggested_clarification")
            )

        except Exception as e:
            return self._create_fallback_analysis(f"Parse error: {str(e)}")

    def _enforce_clarification_policy(self, analysis: ContinuityAnalysis,
                                      previous_intent: TrackedIntent,
                                      new_nlu_result: Dict[str, Any]) -> ContinuityAnalysis:
        """
        Enforce policy that ALL switches require clarification.

        Args:
            analysis: Original analysis from LLM
            previous_intent: Previous intent for context
            new_nlu_result: New NLU result

        Returns:
            Modified analysis with enforced clarification policy
        """
        if analysis.continuity_type in [ContinuityType.INTENT_SWITCH, ContinuityType.CONTEXT_SWITCH]:
            # ALWAYS require clarification for any type of switch
            analysis.requires_clarification = True
            analysis.recommended_action = "clarify"

            # Generate appropriate clarification message if not provided
            if not analysis.suggested_clarification:
                if analysis.continuity_type == ContinuityType.INTENT_SWITCH:
                    analysis.suggested_clarification = (
                        f"I see you were {previous_intent.intent_type.lower()}ing "
                        f"but now want to {new_nlu_result['intent'].lower()}. "
                        f"Should I switch to the new request or continue with the current one?"
                    )
                else:  # CONTEXT_SWITCH
                    prev_target = self._extract_target_summary(previous_intent.entities)
                    new_target = self._extract_target_summary(new_nlu_result.get('entities', {}))
                    analysis.suggested_clarification = (
                        f"I see you were working on {prev_target} "
                        f"but now mention {new_target}. "
                        f"Should I switch focus or do you want both?"
                    )

        elif analysis.continuity_type == ContinuityType.ADDITION:
            # ADDITION might need clarification too for complex cases
            analysis.requires_clarification = True
            analysis.recommended_action = "clarify"

            if not analysis.suggested_clarification:
                analysis.suggested_clarification = (
                    f"Do you want to handle this new {new_nlu_result['intent'].lower()} request "
                    f"in addition to your current {previous_intent.intent_type.lower()} request?"
                )

        elif analysis.continuity_type == ContinuityType.CONTINUATION:
            # CONTINUATION doesn't need clarification
            analysis.requires_clarification = False
            analysis.recommended_action = "continue"

        else:  # UNCLEAR
            analysis.requires_clarification = True
            analysis.recommended_action = "clarify"

        return analysis

    def _extract_target_summary(self, entities: Dict[str, Any]) -> str:
        """Extract a human-readable summary of what the intent targets."""
        if entities.get('product'):
            return entities['product']
        elif entities.get('subcategory'):
            return entities['subcategory']
        elif entities.get('category'):
            return entities['category']
        elif entities.get('order_id'):
            return f"order {entities['order_id']}"
        else:
            return "your request"

    def _fallback_continuity_analysis(self, previous_intent: TrackedIntent,
                                      new_nlu_result: Dict[str, Any],
                                      error_msg: str) -> ContinuityAnalysis:
        """Create fallback analysis when LLM fails."""

        prev_intent_type = previous_intent.intent_type
        new_intent_type = new_nlu_result["intent"]

        # Rule-based fallback with enforced clarification
        if prev_intent_type != new_intent_type:
            # Different intent types = INTENT_SWITCH
            return ContinuityAnalysis(
                continuity_type=ContinuityType.INTENT_SWITCH,
                confidence=0.7,
                reasoning=f"Fallback: Intent type changed ({prev_intent_type} → {new_intent_type})",
                requires_clarification=True,
                suggested_clarification=f"Are you switching from {prev_intent_type} to {new_intent_type}?",
                recommended_action="clarify"
            )
        else:
            # Same intent type - could be continuation or context switch
            # Default to unclear to be safe
            return ContinuityAnalysis(
                continuity_type=ContinuityType.UNCLEAR,
                confidence=0.6,
                reasoning=f"Fallback: Same intent type but uncertain about target change",
                requires_clarification=True,
                suggested_clarification="Could you clarify what you'd like to do?",
                recommended_action="clarify"
            )

    def _create_fallback_analysis(self, reason: str) -> ContinuityAnalysis:
        """Create basic fallback analysis with mandatory clarification."""
        return ContinuityAnalysis(
            continuity_type=ContinuityType.UNCLEAR,
            confidence=0.5,
            reasoning=f"Fallback analysis: {reason}",
            requires_clarification=True,
            suggested_clarification="Could you clarify what you'd like to do?",
            recommended_action="clarify"
        )

    def _start_new_intent(self, intent_type: str, entities: Dict[str, Any], confidence: float) -> Dict[str, Any]:
        """Start tracking a new intent (first intent or no active intents)."""

        new_intent = TrackedIntent(
            intent_type=intent_type,
            entities=entities,
            confidence=confidence
        )

        self.tracked_intents.append(new_intent)
        self.current_intent_index = len(self.tracked_intents) - 1

        return {
            "action": "start_new",
            "intent": new_intent,
            "message": f"I'll help you with {intent_type.lower()}.",
            "requires_clarification": False
        }

    def _process_continuity_result(self, analysis: ContinuityAnalysis,
                                   new_intent_type: str, new_entities: Dict[str, Any],
                                   confidence: float) -> Dict[str, Any]:
        """Process continuity analysis result and take appropriate action."""

        if analysis.continuity_type == ContinuityType.CONTINUATION:
            # Update current intent with new information
            current_intent = self.get_current_intent()
            if current_intent:
                # Merge new entities into current intent
                current_intent.entities.update({k: v for k, v in new_entities.items() if v is not None})
                current_intent.confidence = max(current_intent.confidence, confidence)

            return {
                "action": "continue_current",
                "intent": current_intent,
                "analysis": analysis,
                "message": "I'll continue helping with your current request.",
                "requires_clarification": False
            }

        elif analysis.continuity_type in [ContinuityType.INTENT_SWITCH, ContinuityType.CONTEXT_SWITCH,
                                          ContinuityType.ADDITION]:
            # All switch types require clarification
            return {
                "action": f"clarify_{analysis.continuity_type.value}",
                "analysis": analysis,
                "pending_intent_data": {"type": new_intent_type, "entities": new_entities, "confidence": confidence},
                "message": analysis.suggested_clarification,
                "requires_clarification": True
            }

        else:  # UNCLEAR
            return {
                "action": "clarify_unclear",
                "analysis": analysis,
                "pending_intent_data": {"type": new_intent_type, "entities": new_entities, "confidence": confidence},
                "message": analysis.suggested_clarification or "I'm not sure how this relates to what we were discussing. Could you clarify?",
                "requires_clarification": True
            }

    def _resolve_continue_current(self) -> Dict[str, Any]:
        """Resolve to continue with current intent."""
        current_intent = self.get_current_intent()
        return {
            "action": "continue_current",
            "intent": current_intent,
            "message": "I'll continue with your current request.",
            "requires_clarification": False
        }

    def _resolve_switch_intent(self, new_intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve to switch to new intent."""
        # Mark current intent as abandoned
        current_intent = self.get_current_intent()
        if current_intent:
            current_intent.status = IntentStatus.ABANDONED

        # Create new intent
        new_intent = TrackedIntent(
            intent_type=new_intent_data["type"],
            entities=new_intent_data["entities"],
            confidence=new_intent_data["confidence"]
        )

        self.tracked_intents.append(new_intent)
        self.current_intent_index = len(self.tracked_intents) - 1

        return {
            "action": "switch_intent",
            "intent": new_intent,
            "message": f"I'll help you with {new_intent_data['type'].lower()} instead.",
            "requires_clarification": False
        }

    def _resolve_add_intent(self, new_intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Resolve to add new intent while suspending current."""
        # Suspend current intent
        current_intent = self.get_current_intent()
        if current_intent:
            current_intent.status = IntentStatus.SUSPENDED

        # Create and activate new intent
        new_intent = TrackedIntent(
            intent_type=new_intent_data["type"],
            entities=new_intent_data["entities"],
            confidence=new_intent_data["confidence"]
        )

        self.tracked_intents.append(new_intent)
        self.current_intent_index = len(self.tracked_intents) - 1

        return {
            "action": "add_intent",
            "intent": new_intent,
            "message": f"I'll help you with {new_intent_data['type'].lower()} first, then we can continue with your previous request.",
            "requires_clarification": False
        }


def test_intent_tracker():
    """Test Intent Tracker functionality with both types of switches."""
    print("🧪 Testing Intent Tracker with Switch Types")
    print("=" * 60)

    tracker = IntentTracker()
    conversation_context = []  # Build context progressively

    # Test 1: First intent (no previous context)
    print("1️⃣ First intent - BUY laptop:")
    nlu_result1 = {
        "intent": "BUY",
        "entities": {"category": "electronics", "subcategory": "laptop"},
        "confidence": 0.9
    }

    result1 = tracker.track_new_intent(nlu_result1, conversation_context)
    print(f"   Action: {result1['action']}")
    print(f"   Current intent: {tracker.get_current_intent().get_summary()}")

    # Add to conversation context
    conversation_context.append({"role": "user", "content": "I want to buy a laptop"})

    # Test 2: Intent continuation (refinement)
    print("\n2️⃣ Intent continuation - gaming laptop:")
    conversation_context.append({"role": "system", "content": "What type of laptop are you looking for?"})

    nlu_result2 = {
        "intent": "BUY",
        "entities": {"category": "electronics", "subcategory": "gaming laptop", "budget": "under $2000"},
        "confidence": 0.8
    }

    result2 = tracker.track_new_intent(nlu_result2, conversation_context)
    print(f"   Action: {result2['action']}")
    print(f"   Requires clarification: {result2['requires_clarification']}")
    if result2.get('analysis'):
        print(
            f"   Analysis: {result2['analysis'].continuity_type.value} (confidence: {result2['analysis'].confidence:.2f})")

    conversation_context.append({"role": "user", "content": "Actually a gaming laptop under $2000"})

    # Test 3: INTENT_SWITCH (BUY → RETURN)
    print("\n3️⃣ INTENT_SWITCH - BUY to RETURN:")
    nlu_result3 = {
        "intent": "RETURN",
        "entities": {"order_id": "12345", "return_reason": "defective"},
        "confidence": 0.9
    }

    result3 = tracker.track_new_intent(nlu_result3, conversation_context)
    print(f"   Action: {result3['action']}")
    print(f"   Requires clarification: {result3['requires_clarification']}")
    print(f"   Switch type: {result3.get('analysis', {}).continuity_type.value if result3.get('analysis') else 'N/A'}")
    if result3['requires_clarification']:
        print(f"   Clarification: {result3['message'][:80]}...")

    conversation_context.append({"role": "user", "content": "Actually I want to return my phone instead"})

    # Test 4: Resolve INTENT_SWITCH
    print("\n4️⃣ Resolving INTENT_SWITCH - user switches:")
    if result3.get('analysis'):
        resolution = tracker.resolve_clarification(
            "switch to new",
            result3['analysis'],
            {"type": "RETURN", "entities": nlu_result3['entities'], "confidence": 0.9}
        )
        print(f"   Resolution action: {resolution['action']}")
        print(f"   New current intent: {tracker.get_current_intent().get_summary()}")
        print(f"   Previous intent status: {tracker.tracked_intents[0].status.value}")

    conversation_context.append({"role": "user", "content": "switch to new"})
    conversation_context.append({"role": "system", "content": "I'll help you with return instead."})

    # Test 5: CONTEXT_SWITCH (Return order1 → Return order2)
    print("\n5️⃣ CONTEXT_SWITCH - same intent, different target:")
    nlu_result5 = {
        "intent": "RETURN",
        "entities": {"order_id": "67890", "return_reason": "wrong size"},
        "confidence": 0.85
    }

    result5 = tracker.track_new_intent(nlu_result5, conversation_context)
    print(f"   Action: {result5['action']}")
    print(f"   Requires clarification: {result5['requires_clarification']}")
    print(f"   Switch type: {result5.get('analysis', {}).continuity_type.value if result5.get('analysis') else 'N/A'}")
    if result5['requires_clarification']:
        print(f"   Clarification: {result5['message'][:80]}...")

    # Test 6: Intent tracking summary
    print("\n6️⃣ Intent tracking summary:")
    print(f"   Total intents tracked: {len(tracker.tracked_intents)}")
    for i, intent in enumerate(tracker.tracked_intents):
        print(f"   {i + 1}. {intent.get_summary()} - {intent.status.value}")

    print(f"   Final conversation length: {len(conversation_context)} messages")

    print("\n" + "=" * 60)
    print("✅ Intent Tracker Tests Complete!")


if __name__ == "__main__":
    test_intent_tracker()