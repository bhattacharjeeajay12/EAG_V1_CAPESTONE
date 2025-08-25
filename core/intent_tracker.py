# core/intent_tracker.py
"""
Intent Tracker with LLM-Powered Continuity Analysis and Advanced Features

Purpose: Tracks user intents throughout the conversation with sophisticated handling
of intent continuity, context switches, entity conflicts, and priority management.
Provides rollback capabilities and maintains conversation context state.

Key Enhancements:
- Nuanced Context Switch handling (replace vs add vs compare)
- Smart entity merge with conflict resolution
- Intent priority and urgency management
- Rollback/undo functionality
- Conversation context state management
- Improved clarification strategies
"""

import json
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Tuple
from enum import Enum
from datetime import datetime
from core.llm_client import LLMClient


class IntentStatus(Enum):
    """Status of tracked intents."""
    ACTIVE = "active"  # Currently being worked on
    SUSPENDED = "suspended"  # Temporarily paused
    COMPLETED = "completed"  # Successfully finished
    ABANDONED = "abandoned"  # User cancelled/switched away


class IntentPriority(Enum):
    """Priority levels for intents."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class ContinuityType(Enum):
    """Types of intent continuity relationships."""
    CONTINUATION = "continuation"  # Same intent, refinement/clarification
    INTENT_SWITCH = "intent_switch"  # Different intent types (BUY → RETURN)
    CONTEXT_SWITCH = "context_switch"  # Same intent, different target (Buy laptop → Buy cupboard)
    ADDITION = "addition"  # New intent while keeping previous
    UNCLEAR = "unclear"  # Ambiguous, needs user clarification


class ContextSwitchType(Enum):
    """Types of context switch handling."""
    REPLACE = "replace"  # Replace current target with new one
    ADD = "add"  # Add new target to current intent
    COMPARE = "compare"  # Compare current vs new target
    SEPARATE = "separate"  # Handle as separate intent


@dataclass
class TrackedIntent:
    """Represents a user intent being tracked through conversation."""

    intent_type: str  # BUY, ORDER, RECOMMEND, RETURN
    entities: Dict[str, Any]  # Extracted entities
    status: IntentStatus = IntentStatus.ACTIVE
    priority: IntentPriority = IntentPriority.NORMAL
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    last_updated: str = field(default_factory=lambda: datetime.now().isoformat())
    context_data: Dict[str, Any] = field(default_factory=dict)
    entity_history: List[Dict[str, Any]] = field(default_factory=list)  # Track entity changes

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
        priority_str = f" [{self.priority.value}]" if self.priority != IntentPriority.NORMAL else ""
        return f"{self.intent_type}{entity_str}{priority_str}"

    def update_entities(self, new_entities: Dict[str, Any], merge_strategy: str = "smart") -> Dict[str, Any]:
        """
        Update entities with conflict resolution.

        Args:
            new_entities: New entities to merge
            merge_strategy: "replace", "merge", "smart", or "ask"

        Returns:
            Dictionary with conflicts that need user clarification
        """
        # Store current entities in history before updating
        self.entity_history.append({
            "timestamp": self.last_updated,
            "entities": self.entities.copy(),
            "action": "pre_update_snapshot"
        })

        conflicts = {}

        for key, new_value in new_entities.items():
            if new_value is None:
                continue

            existing_value = self.entities.get(key)

            if existing_value is None:
                # No conflict - just add new value
                self.entities[key] = new_value

            elif existing_value != new_value:
                # Conflict detected
                if merge_strategy == "replace":
                    self.entities[key] = new_value
                elif merge_strategy == "merge" and isinstance(existing_value, list) and isinstance(new_value, list):
                    # Merge lists
                    merged = list(set(existing_value + new_value))
                    self.entities[key] = merged
                elif merge_strategy == "smart":
                    # Smart resolution based on entity type
                    resolved_value, needs_clarification = self._smart_entity_resolution(key, existing_value, new_value)
                    self.entities[key] = resolved_value
                    if needs_clarification:
                        conflicts[key] = {"old": existing_value, "new": new_value, "resolved": resolved_value}
                else:  # merge_strategy == "ask"
                    conflicts[key] = {"old": existing_value, "new": new_value}

        self.last_updated = datetime.now().isoformat()
        return conflicts

    def _smart_entity_resolution(self, key: str, old_value: Any, new_value: Any) -> Tuple[Any, bool]:
        """
        Smart entity conflict resolution.

        Returns:
            Tuple of (resolved_value, needs_clarification)
        """
        # Budget: take higher value (user likely expanding budget)
        if key == "budget" and isinstance(old_value, str) and isinstance(new_value, str):
            # Simple heuristic: if new budget mentions higher number, use it
            if "under" in new_value.lower() or "below" in new_value.lower():
                return new_value, False  # User refined budget
            return new_value, True  # Unclear which budget to use

        # Specifications: merge lists
        if key == "specifications" and isinstance(old_value, list) and isinstance(new_value, list):
            merged = list(set(old_value + new_value))
            return merged, False

        # Category/subcategory: new value likely more specific
        if key in ["category", "subcategory", "product"]:
            return new_value, True  # Usually needs clarification

        # Default: use new value but flag for clarification
        return new_value, True


@dataclass
class ContinuityAnalysis:
    """Result of intent continuity analysis with enhanced context."""

    continuity_type: ContinuityType
    confidence: float
    reasoning: str
    requires_clarification: bool = False
    suggested_clarification: Optional[str] = None
    recommended_action: str = "continue"
    context_switch_options: List[ContextSwitchType] = field(default_factory=list)  # For CONTEXT_SWITCH
    urgency_detected: bool = False
    priority_level: IntentPriority = IntentPriority.NORMAL


@dataclass
class IntentSnapshot:
    """Snapshot of intent tracker state for rollback."""

    timestamp: str
    tracked_intents: List[TrackedIntent]
    current_intent_index: Optional[int]
    conversation_context: List[Dict[str, Any]]
    action_description: str


class IntentTracker:
    """
    Advanced intent tracker with sophisticated continuity analysis and state management.
    """

    def __init__(self, llm_client: Optional[LLMClient] = None):
        """Initialize Intent Tracker with enhanced capabilities."""
        self.llm_client = llm_client or LLMClient()
        self.tracked_intents: List[TrackedIntent] = []
        self.current_intent_index: Optional[int] = None
        self.conversation_context: List[Dict[str, Any]] = []

        # Enhanced features
        self.intent_snapshots: List[IntentSnapshot] = []  # For rollback
        self.max_snapshots = 10
        self.pending_entity_conflicts: Dict[str, Any] = {}

        # Priority keywords for urgency detection
        self.urgency_keywords = ["urgent", "emergency", "asap", "immediately", "critical", "rush"]

    def analyze_intent_continuity(self, previous_intent: TrackedIntent,
                                  new_nlu_result: Dict[str, Any],
                                  conversation_context: List[Dict]) -> ContinuityAnalysis:
        """Enhanced intent continuity analysis with priority and urgency detection."""

        # Detect urgency in user message
        user_message = self._extract_user_message_from_context(conversation_context)
        urgency_detected, priority_level = self._detect_urgency_and_priority(user_message)

        try:
            # Create enhanced LLM prompt
            prompt = self._create_enhanced_continuity_prompt(
                previous_intent, new_nlu_result, conversation_context, urgency_detected
            )

            # Get LLM analysis
            llm_response = self.llm_client.generate(prompt)

            # Parse response with enhanced features
            analysis = self._parse_enhanced_continuity_response(llm_response)

            # Apply urgency and priority
            analysis.urgency_detected = urgency_detected
            analysis.priority_level = priority_level

            # Enforce clarification policy
            analysis = self._enforce_enhanced_clarification_policy(analysis, previous_intent, new_nlu_result)

            return analysis

        except Exception as e:
            return self._fallback_continuity_analysis(previous_intent, new_nlu_result, str(e))

    def track_new_intent(self, nlu_result: Dict[str, Any],
                         conversation_context: List[Dict]) -> Dict[str, Any]:
        """Enhanced intent tracking with snapshot management."""

        # Update internal conversation context
        self.conversation_context = conversation_context.copy()

        # Create snapshot before making changes
        self._create_snapshot("before_intent_tracking")

        new_intent_type = nlu_result["intent"]
        new_entities = nlu_result.get("entities", {})
        confidence = nlu_result.get("confidence", 0.5)

        # If no previous intent, start tracking this one
        if not self.tracked_intents or self.current_intent_index is None:
            return self._start_new_intent(new_intent_type, new_entities, confidence)

        # Get current active intent
        current_intent = self.tracked_intents[self.current_intent_index]

        # Analyze continuity with enhanced features
        continuity_analysis = self.analyze_intent_continuity(
            current_intent, nlu_result, conversation_context
        )

        # Handle urgent intents with priority
        if continuity_analysis.urgency_detected:
            return self._handle_urgent_intent(continuity_analysis, new_intent_type, new_entities, confidence)

        # Process based on continuity type
        return self._process_enhanced_continuity_result(
            continuity_analysis, new_intent_type, new_entities, confidence
        )

    def resolve_clarification(self, user_response: str, pending_analysis: ContinuityAnalysis,
                              new_intent_data: Dict[str, Any]) -> Dict[str, Any]:
        """Enhanced clarification resolution with rollback support."""

        # Create snapshot before resolution
        self._create_snapshot("before_clarification_resolution")

        response_lower = user_response.lower()

        # Handle rollback requests
        if any(word in response_lower for word in ["undo", "rollback", "go back", "cancel that"]):
            return self._handle_rollback_request()

        # Parse user choice for context switches with more options
        if pending_analysis.continuity_type == ContinuityType.CONTEXT_SWITCH:
            return self._resolve_context_switch_clarification(user_response, new_intent_data)

        # Standard clarification resolution
        if any(word in response_lower for word in ["continue", "same", "current", "keep"]):
            return self._resolve_continue_current()

        elif any(word in response_lower for word in ["switch", "new", "change", "different"]):
            return self._execute_switch_action(
                pending_analysis.continuity_type,
                new_intent_data["type"],
                new_intent_data["entities"],
                new_intent_data["confidence"]
            )

        elif any(word in response_lower for word in ["both", "add", "also", "too"]):
            return self._resolve_add_intent(new_intent_data)

        else:
            return {
                "action": "re_clarify",
                "message": "I didn't understand. Please say: 'continue', 'switch', 'both', or 'undo'",
                "requires_clarification": True
            }

    def rollback_to_previous_state(self, steps_back: int = 1) -> Dict[str, Any]:
        """Rollback to previous intent tracker state."""

        if steps_back < 1:
            return {
                "action": "rollback_failed",
                "message": "Steps back must be at least 1.",
                "requires_clarification": False
            }

        if len(self.intent_snapshots) < steps_back:
            return {
                "action": "rollback_failed",
                "message": f"Cannot rollback {steps_back} step{'s' if steps_back > 1 else ''}. Only {len(self.intent_snapshots)} snapshot{'s' if len(self.intent_snapshots) != 1 else ''} available.",
                "requires_clarification": False
            }

        # Get snapshot to restore
        snapshot = self.intent_snapshots[-(steps_back)]

        try:
            # Restore state with deep copy to avoid reference issues
            self.tracked_intents = [
                TrackedIntent(
                    intent_type=intent.intent_type,
                    entities=intent.entities.copy(),
                    status=intent.status,
                    priority=intent.priority,
                    confidence=intent.confidence,
                    created_at=intent.created_at,
                    last_updated=intent.last_updated,
                    context_data=intent.context_data.copy(),
                    entity_history=intent.entity_history.copy()
                ) for intent in snapshot.tracked_intents
            ]
            self.current_intent_index = snapshot.current_intent_index
            self.conversation_context = snapshot.conversation_context.copy()

            # Remove the snapshots after the rollback point
            self.intent_snapshots = self.intent_snapshots[:-(steps_back)]

            return {
                "action": "rollback_completed",
                "message": f"I've rolled back to: {snapshot.action_description}",
                "restored_intent": self.get_current_intent(),
                "requires_clarification": False
            }

        except Exception as e:
            return {
                "action": "rollback_failed",
                "message": f"Failed to rollback due to an error: {str(e)}",
                "requires_clarification": False
            }


    def _detect_urgency_and_priority(self, user_message: str) -> Tuple[bool, IntentPriority]:
        """Detect urgency and determine priority level."""
        if not user_message:
            return False, IntentPriority.NORMAL

        message_lower = user_message.lower()

        # Check for urgency keywords
        urgency_detected = any(keyword in message_lower for keyword in self.urgency_keywords)

        if urgency_detected:
            # Determine priority level based on context
            if any(word in message_lower for word in ["emergency", "critical"]):
                return True, IntentPriority.URGENT
            elif any(word in message_lower for word in ["urgent", "asap", "immediately"]):
                return True, IntentPriority.HIGH
            else:
                return True, IntentPriority.HIGH

        return False, IntentPriority.NORMAL

    def _handle_urgent_intent(self, analysis: ContinuityAnalysis, intent_type: str,
                              entities: Dict[str, Any], confidence: float) -> Dict[str, Any]:
        """Handle urgent intents with priority processing."""

        # For urgent intents, suspend current and handle immediately
        current_intent = self.get_current_intent()
        if current_intent:
            current_intent.status = IntentStatus.SUSPENDED

        # Create urgent intent
        urgent_intent = TrackedIntent(
            intent_type=intent_type,
            entities=entities,
            confidence=confidence,
            priority=analysis.priority_level
        )

        self.tracked_intents.append(urgent_intent)
        self.current_intent_index = len(self.tracked_intents) - 1

        return {
            "action": "urgent_intent_activated",
            "intent": urgent_intent,
            "message": f"I understand this is {analysis.priority_level.value} priority. I'll handle your {intent_type.lower()} request immediately.",
            "requires_clarification": False,
            "priority": analysis.priority_level.value
        }

    def _resolve_context_switch_clarification(self, user_response: str, new_intent_data: Dict[str, Any]) -> Dict[
        str, Any]:
        """Resolve context switch with multiple options."""

        response_lower = user_response.lower()

        if any(word in response_lower for word in ["replace", "switch", "change"]):
            # Replace current target with new one
            current_intent = self.get_current_intent()
            if current_intent:
                conflicts = current_intent.update_entities(new_intent_data["entities"], "replace")

                return {
                    "action": "context_replaced",
                    "intent": current_intent,
                    "message": f"I've updated your {current_intent.intent_type.lower()} request with the new details.",
                    "requires_clarification": False,
                    "entity_conflicts": conflicts
                }

        elif any(word in response_lower for word in ["add", "both", "include"]):
            # Add to current intent (expand scope)
            current_intent = self.get_current_intent()
            if current_intent:
                # Smart merge entities
                conflicts = current_intent.update_entities(new_intent_data["entities"], "merge")

                return {
                    "action": "context_expanded",
                    "intent": current_intent,
                    "message": f"I've expanded your {current_intent.intent_type.lower()} request to include both options.",
                    "requires_clarification": False,
                    "entity_conflicts": conflicts
                }

        elif any(word in response_lower for word in ["compare", "comparison"]):
            # Add comparison context
            current_intent = self.get_current_intent()
            if current_intent:
                current_intent.entities["comparison_items"] = current_intent.entities.get("comparison_items", [])
                new_product = self._extract_target_summary(new_intent_data["entities"])
                current_intent.entities["comparison_items"].append(new_product)

                return {
                    "action": "comparison_added",
                    "intent": current_intent,
                    "message": f"I'll help you compare your options for {current_intent.intent_type.lower()}.",
                    "requires_clarification": False
                }

        elif any(word in response_lower for word in ["separate", "different", "new"]):
            # Handle as separate intent
            return self._resolve_add_intent(new_intent_data)

        else:
            # Unclear - provide specific context switch options
            current_intent = self.get_current_intent()
            if not current_intent:
                return {
                    "action": "error",
                    "message": "No current intent found to perform context switch.",
                    "requires_clarification": False
                }

            current_target = self._extract_target_summary(current_intent.entities)
            new_target = self._extract_target_summary(new_intent_data["entities"])

            return {
                "action": "re_clarify_context_switch",
                "message": f"For {current_target} vs {new_target}, would you like to:\n"
                           f"• 'Replace' - switch from {current_target} to {new_target}\n"
                           f"• 'Add' - include both {current_target} and {new_target}\n"
                           f"• 'Compare' - compare {current_target} vs {new_target}\n"
                           f"• 'Separate' - handle {new_target} as a separate request",
                "requires_clarification": True
            }

    def _create_enhanced_continuity_prompt(self, previous_intent: TrackedIntent,
                                           new_nlu_result: Dict[str, Any],
                                           conversation_context: List[Dict],
                                           urgency_detected: bool) -> str:
        """Create enhanced LLM prompt with urgency and context switch detection."""

        context_str = "\n".join([
            f"{msg.get('role', 'unknown')}: {msg.get('content', '')}"
            for msg in conversation_context[-5:] if msg.get('content')  # Filter out empty content
        ]) if conversation_context else "No previous conversation"

        urgency_note = "\n⚠️ URGENT REQUEST DETECTED - Consider priority handling" if urgency_detected else ""

        prompt = f"""
You are an expert conversation analyst. Analyze how a new user message relates to their previous intent.

PREVIOUS INTENT:
- Type: {previous_intent.intent_type}
- Details: {previous_intent.get_summary()}
- Status: {previous_intent.status.value}
- Priority: {previous_intent.priority.value}

NEW MESSAGE ANALYSIS:
- Intent: {new_nlu_result.get('intent', 'UNKNOWN')}
- Entities: {new_nlu_result.get('entities', {})}
- Confidence: {new_nlu_result.get('confidence', 0.5)}

RECENT CONVERSATION:
{context_str}{urgency_note}

ANALYSIS TASK:
Determine the relationship between the previous intent and new message:

1. CONTINUATION - Same goal, refinement (e.g., "laptop" → "gaming laptop under $1000")

2. INTENT_SWITCH - Different intent types (e.g., "buy laptop" → "return phone")

3. CONTEXT_SWITCH - Same intent, different target (e.g., "buy laptop" → "buy cupboard")
   For CONTEXT_SWITCH, suggest options: REPLACE, ADD, COMPARE, or SEPARATE

4. ADDITION - New goal while keeping previous (e.g., "buy laptop" → "also check return policy")

5. UNCLEAR - Ambiguous, needs clarification

SPECIAL CONSIDERATIONS:
- If urgency detected, prioritize immediate handling
- For CONTEXT_SWITCH, consider whether user wants to replace, add, compare, or separate
- Look for entity conflicts that need resolution
- Consider conversation flow and user frustration indicators

Return JSON:
{{
  "continuity_type": "CONTINUATION|INTENT_SWITCH|CONTEXT_SWITCH|ADDITION|UNCLEAR",
  "confidence": 0.0-1.0,
  "reasoning": "detailed_explanation_of_analysis",
  "suggested_clarification": "question_to_ask_user_or_null",
  "context_switch_options": ["REPLACE", "ADD", "COMPARE", "SEPARATE"],
  "entity_conflicts_detected": ["list_of_conflicting_entity_keys"],
  "urgency_indicators": ["list_of_urgency_signals_found"]
}}

Be precise and consider the user's mental model and conversation flow.
"""
        return prompt

    def _parse_enhanced_continuity_response(self, llm_response: str) -> ContinuityAnalysis:
        """Parse LLM response with enhanced features."""

        if not llm_response or llm_response.startswith("[LLM-FALLBACK]"):
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
            json_start = response.find('{')
            json_end = response.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                raise ValueError("No JSON found in response")

            json_str = response[json_start:json_end]
            parsed = json.loads(json_str)

            # Create enhanced ContinuityAnalysis
            continuity_type_str = parsed.get("continuity_type", "UNCLEAR")
            try:
                continuity_type = ContinuityType(continuity_type_str.lower())
            except ValueError:
                continuity_type = ContinuityType.UNCLEAR

            # Parse context switch options with better error handling
            context_switch_options = []
            for option in parsed.get("context_switch_options", []):
                try:
                    if isinstance(option, str):
                        context_switch_options.append(ContextSwitchType(option.lower()))
                except (ValueError, AttributeError):
                    continue

            # Validate confidence range
            confidence = parsed.get("confidence", 0.5)
            try:
                confidence = max(0.0, min(1.0, float(confidence)))
            except (ValueError, TypeError):
                confidence = 0.5

            return ContinuityAnalysis(
                continuity_type=continuity_type,
                confidence=confidence,
                reasoning=parsed.get("reasoning", "Enhanced LLM analysis completed"),
                suggested_clarification=parsed.get("suggested_clarification"),
                context_switch_options=context_switch_options
            )

        except (json.JSONDecodeError, KeyError, ValueError) as e:
            return self._create_fallback_analysis(f"Parse error: {str(e)}")
        except Exception as e:
            return self._create_fallback_analysis(f"Unexpected error: {str(e)}")

    def _create_snapshot(self, action_description: str) -> None:
        """Create snapshot of current state for rollback."""

        # Deep copy tracked intents to avoid reference issues
        intents_copy = []
        for intent in self.tracked_intents:
            intent_copy = TrackedIntent(
                intent_type=intent.intent_type,
                entities=intent.entities.copy(),
                status=intent.status,
                priority=intent.priority,
                confidence=intent.confidence,
                created_at=intent.created_at,
                last_updated=intent.last_updated,
                context_data=intent.context_data.copy(),
                entity_history=intent.entity_history.copy()
            )
            intents_copy.append(intent_copy)

        snapshot = IntentSnapshot(
            timestamp=datetime.now().isoformat(),
            tracked_intents=intents_copy,
            current_intent_index=self.current_intent_index,
            conversation_context=self.conversation_context.copy(),
            action_description=action_description
        )

        self.intent_snapshots.append(snapshot)

        # Keep only recent snapshots
        if len(self.intent_snapshots) > self.max_snapshots:
            self.intent_snapshots = self.intent_snapshots[-self.max_snapshots:]

    def _handle_rollback_request(self) -> Dict[str, Any]:
        """Handle user rollback request."""

        if not self.intent_snapshots:
            return {
                "action": "rollback_unavailable",
                "message": "I don't have any previous states to rollback to.",
                "requires_clarification": False
            }

        return self.rollback_to_previous_state(1)

    def _extract_user_message_from_context(self, conversation_context: List[Dict]) -> str:
        """Extract the most recent user message from conversation context."""

        if not conversation_context:
            return ""

        for msg in reversed(conversation_context):
            if msg.get("role") == "user" and msg.get("content"):
                return msg["content"]

        return ""

    # Include all other methods from the original implementation with same logic
    # (get_current_intent, complete_current_intent, _enforce_enhanced_clarification_policy,
    #  _process_enhanced_continuity_result, _execute_switch_action, _resolve_continue_current,
    #  _resolve_switch_intent, _resolve_add_intent, _start_new_intent, etc.)

    def get_current_intent(self) -> Optional[TrackedIntent]:
        """Get currently active intent."""
        if self.current_intent_index is not None and self.current_intent_index < len(self.tracked_intents):
            return self.tracked_intents[self.current_intent_index]
        return None

    def complete_current_intent(self) -> Optional[TrackedIntent]:
        """Mark current intent as completed and activate any suspended intents."""
        current = self.get_current_intent()
        if current:
            current.status = IntentStatus.COMPLETED

            # Look for suspended intents to reactivate (prioritize by priority)
            suspended_intents = [(i, intent) for i, intent in enumerate(self.tracked_intents)
                                 if intent.status == IntentStatus.SUSPENDED]

            if suspended_intents:
                # Sort by priority (URGENT > HIGH > NORMAL > LOW)
                priority_order = {IntentPriority.URGENT: 4, IntentPriority.HIGH: 3,
                                  IntentPriority.NORMAL: 2, IntentPriority.LOW: 1}
                suspended_intents.sort(key=lambda x: priority_order.get(x[1].priority, 0), reverse=True)

                # Activate highest priority suspended intent
                intent_index, intent = suspended_intents[0]
                intent.status = IntentStatus.ACTIVE
                self.current_intent_index = intent_index
                return intent

            self.current_intent_index = None

        return None

    # ... (other methods remain the same as the original implementation)

    def _enforce_enhanced_clarification_policy(self, analysis: ContinuityAnalysis,
                                               previous_intent: TrackedIntent,
                                               new_nlu_result: Dict[str, Any]) -> ContinuityAnalysis:
        """Enhanced clarification policy with context switch options."""

        if analysis.continuity_type in [ContinuityType.INTENT_SWITCH, ContinuityType.CONTEXT_SWITCH]:
            analysis.requires_clarification = True
            analysis.recommended_action = "clarify"

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
                        f"I see you were working on {prev_target} but now mention {new_target}. "
                        f"Would you like to:\n"
                        f"• Replace {prev_target} with {new_target}\n"
                        f"• Add {new_target} to your current request\n"
                        f"• Compare {prev_target} vs {new_target}\n"
                        f"• Handle {new_target} as a separate request"
                    )

        elif analysis.continuity_type == ContinuityType.ADDITION:
            analysis.requires_clarification = True
            analysis.recommended_action = "clarify"

            if not analysis.suggested_clarification:
                analysis.suggested_clarification = (
                    f"Do you want to handle this new {new_nlu_result['intent'].lower()} request "
                    f"in addition to your current {previous_intent.intent_type.lower()} request?"
                )

        elif analysis.continuity_type == ContinuityType.CONTINUATION:
            analysis.requires_clarification = False
            analysis.recommended_action = "continue"

        else:  # UNCLEAR
            analysis.requires_clarification = True
            analysis.recommended_action = "clarify"

        return analysis

    def _process_enhanced_continuity_result(self, analysis: ContinuityAnalysis,
                                            new_intent_type: str, new_entities: Dict[str, Any],
                                            confidence: float) -> Dict[str, Any]:
        """Process continuity analysis with enhanced features."""

        if analysis.continuity_type == ContinuityType.CONTINUATION:
            current_intent = self.get_current_intent()
            if current_intent:
                # Smart entity merge with conflict detection
                conflicts = current_intent.update_entities(new_entities, "smart")

                response = {
                    "action": "continue_current",
                    "intent": current_intent,
                    "analysis": analysis,
                    "message": "I'll continue helping with your current request.",
                    "requires_clarification": False
                }

                # Handle entity conflicts if any
                if conflicts:
                    self.pending_entity_conflicts = conflicts
                    response["entity_conflicts"] = conflicts
                    response["message"] += f" I noticed some conflicting details that we should clarify."

                return response

        elif analysis.continuity_type in [ContinuityType.INTENT_SWITCH, ContinuityType.CONTEXT_SWITCH,
                                          ContinuityType.ADDITION]:
            if analysis.requires_clarification:
                return {
                    "action": f"clarify_{analysis.continuity_type.value}",
                    "analysis": analysis,
                    "pending_intent_data": {"type": new_intent_type, "entities": new_entities,
                                            "confidence": confidence},
                    "message": analysis.suggested_clarification,
                    "requires_clarification": True,
                    "context_switch_options": [opt.value for opt in analysis.context_switch_options]
                }
            else:
                return self._execute_switch_action(analysis.continuity_type, new_intent_type, new_entities, confidence)

        else:  # UNCLEAR
            return {
                "action": "clarify_unclear",
                "analysis": analysis,
                "pending_intent_data": {"type": new_intent_type, "entities": new_entities, "confidence": confidence},
                "message": analysis.suggested_clarification or "I'm not sure how this relates to what we were discussing. Could you clarify?",
                "requires_clarification": True
            }

    def _execute_switch_action(self, switch_type: ContinuityType, new_intent_type: str,
                               new_entities: Dict[str, Any], confidence: float) -> Dict[str, Any]:
        """Execute switch action with enhanced handling."""

        if switch_type == ContinuityType.INTENT_SWITCH:
            return self._resolve_switch_intent(
                {"type": new_intent_type, "entities": new_entities, "confidence": confidence})

        elif switch_type == ContinuityType.CONTEXT_SWITCH:
            return self._resolve_switch_intent(
                {"type": new_intent_type, "entities": new_entities, "confidence": confidence})

        elif switch_type == ContinuityType.ADDITION:
            return self._resolve_add_intent(
                {"type": new_intent_type, "entities": new_entities, "confidence": confidence})

        else:
            return {
                "action": "error",
                "message": f"Unknown switch type: {switch_type}",
                "requires_clarification": False
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
        current_intent = self.get_current_intent()
        if current_intent:
            current_intent.status = IntentStatus.ABANDONED

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
        current_intent = self.get_current_intent()
        if current_intent:
            current_intent.status = IntentStatus.SUSPENDED

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

    def _start_new_intent(self, intent_type: str, entities: Dict[str, Any], confidence: float) -> Dict[str, Any]:
        """Start tracking a new intent."""

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

    def _extract_target_summary(self, entities: Dict[str, Any]) -> str:
        """Extract human-readable summary of what the intent targets."""
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

        if prev_intent_type != new_intent_type:
            return ContinuityAnalysis(
                continuity_type=ContinuityType.INTENT_SWITCH,
                confidence=0.7,
                reasoning=f"Fallback: Intent type changed ({prev_intent_type} → {new_intent_type})",
                requires_clarification=True,
                suggested_clarification=f"Are you switching from {prev_intent_type} to {new_intent_type}?",
                recommended_action="clarify"
            )
        else:
            return ContinuityAnalysis(
                continuity_type=ContinuityType.UNCLEAR,
                confidence=0.6,
                reasoning=f"Fallback: Same intent type but uncertain about target change",
                requires_clarification=True,
                suggested_clarification="Could you clarify what you'd like to do?",
                recommended_action="clarify"
            )

    def _create_fallback_analysis(self, reason: str) -> ContinuityAnalysis:
        """Create basic fallback analysis."""
        return ContinuityAnalysis(
            continuity_type=ContinuityType.UNCLEAR,
            confidence=0.5,
            reasoning=f"Fallback analysis: {reason}",
            requires_clarification=True,
            suggested_clarification="Could you clarify what you'd like to do?",
            recommended_action="clarify"
        )


def test_enhanced_intent_tracker():
    """Test the enhanced Intent Tracker with all new features."""
    print("🧪 Testing Enhanced Intent Tracker")
    print("=" * 60)

    tracker = IntentTracker()
    conversation_context = []

    # Test 1: First intent
    print("1️⃣ First intent - BUY laptop:")
    nlu_result1 = {
        "intent": "BUY",
        "entities": {"category": "electronics", "subcategory": "laptop", "budget": "under $1000"},
        "confidence": 0.9
    }

    result1 = tracker.track_new_intent(nlu_result1, conversation_context)
    print(f"   Action: {result1['action']}")
    print(f"   Current intent: {tracker.get_current_intent().get_summary()}")

    conversation_context.append({"role": "user", "content": "I want to buy a laptop under $1000"})

    # Test 2: Entity conflict (budget change)
    print("\n2️⃣ Entity conflict - budget refinement:")
    conversation_context.append({"role": "system", "content": "What type of laptop are you looking for?"})

    nlu_result2 = {
        "intent": "BUY",
        "entities": {"category": "electronics", "subcategory": "gaming laptop", "budget": "under $2000"},
        "confidence": 0.8
    }

    result2 = tracker.track_new_intent(nlu_result2, conversation_context)
    print(f"   Action: {result2['action']}")
    print(f"   Entity conflicts: {result2.get('entity_conflicts', 'None')}")

    conversation_context.append({"role": "user", "content": "Actually a gaming laptop under $2000"})

    # Test 3: Urgent intent switch
    print("\n3️⃣ Urgent intent - track order:")
    nlu_result3 = {
        "intent": "ORDER",
        "entities": {"order_id": "URGENT123"},
        "confidence": 0.9
    }

    conversation_context.append({"role": "user", "content": "URGENT - where is my order URGENT123?"})

    result3 = tracker.track_new_intent(nlu_result3, conversation_context)
    print(f"   Action: {result3['action']}")
    print(f"   Priority: {result3.get('priority', 'normal')}")
    print(f"   Current intent: {tracker.get_current_intent().get_summary()}")

    # Test 4: Context switch with options
    print("\n4️⃣ Context switch - different order:")
    nlu_result4 = {
        "intent": "ORDER",
        "entities": {"order_id": "ORD456"},
        "confidence": 0.85
    }

    result4 = tracker.track_new_intent(nlu_result4, conversation_context)
    print(f"   Action: {result4['action']}")
    print(f"   Switch type: {result4.get('analysis', {}).continuity_type.value if result4.get('analysis') else 'N/A'}")
    print(f"   Options: {result4.get('context_switch_options', [])}")

    # Test 5: Rollback functionality
    print("\n5️⃣ Testing rollback:")
    rollback_result = tracker.rollback_to_previous_state(1)
    print(f"   Action: {rollback_result['action']}")
    print(f"   Current intent after rollback: {tracker.get_current_intent().get_summary()}")

    # Test 6: Enhanced summary
    print("\n6️⃣ Enhanced tracking summary:")
    print(f"   Total intents tracked: {len(tracker.tracked_intents)}")
    print(f"   Snapshots available: {len(tracker.intent_snapshots)}")
    for i, intent in enumerate(tracker.tracked_intents):
        print(f"   {i + 1}. {intent.get_summary()} - {intent.status.value}")
        if intent.entity_history:
            print(f"       Entity history: {len(intent.entity_history)} changes")

    print("\n" + "=" * 60)
    print("✅ Enhanced Intent Tracker Tests Complete!")


if __name__ == "__main__":
    test_enhanced_intent_tracker()