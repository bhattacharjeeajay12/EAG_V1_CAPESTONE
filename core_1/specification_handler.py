# core_1/specification_handler.py
"""
Handles specification gathering, entity extraction, and requirement confirmation.
Manages the complete specification collection workflow.
"""

import re
from typing import Dict, List, Any, Optional
from .schemas import SpecificationSchema
from .models import PlannerDecision


class SpecificationHandler:
    """Handles specification gathering with enhanced entity mapping and validation."""

    def __init__(self):
        self.required_specs: Dict[str, Any] = {}
        self.gathered_specs: Dict[str, Any] = {}
        self.specs_confirmed: bool = False

    def reset_specifications(self):
        """Reset specification gathering state."""
        self.required_specs = {}
        self.gathered_specs = {}
        self.specs_confirmed = False

    def start_specification_gathering(self, needed_specs: List[str]) -> Dict[str, str]:
        """Initialize specification gathering with validated spec names."""
        validated_specs = SpecificationSchema.validate_spec_names(needed_specs)
        self.required_specs = {spec: None for spec in validated_specs}
        return self.required_specs

    def extract_additional_entities(self, user_message: str) -> Dict[str, Any]:
        """Extract additional entities that NLU might miss using pattern matching."""
        message_lower = user_message.lower()
        additional_entities = {}

        # Extract use case patterns
        gaming_keywords = ["gaming", "games", "game", "esports", "streaming"]
        work_keywords = ["work", "office", "business", "professional", "productivity"]
        study_keywords = ["study", "studies", "education", "student", "school", "college"]

        if any(keyword in message_lower for keyword in gaming_keywords):
            additional_entities["use_case"] = "gaming"
        elif any(keyword in message_lower for keyword in work_keywords):
            additional_entities["use_case"] = "work"
        elif any(keyword in message_lower for keyword in study_keywords):
            additional_entities["use_case"] = "study"

        # Extract budget patterns (INR, USD, etc.)
        budget_patterns = [
            r'(\d+(?:,\d+)*)\s*(?:inr|rupees|rs\.?)',
            r'(?:inr|rs\.?)\s*(\d+(?:,\d+)*)',
            r'(\d+(?:,\d+)*)\s*(?:usd|dollars?|\$)',
            r'(?:\$|usd)\s*(\d+(?:,\d+)*)',
            r'budget.*?(\d+(?:,\d+)*)',
            r'around\s+(\d+(?:,\d+)*)',
            r'up\s+to\s+(\d+(?:,\d+)*)'
        ]

        for pattern in budget_patterns:
            match = re.search(pattern, message_lower)
            if match:
                budget_amount = match.group(1).replace(',', '')
                if 'inr' in message_lower or 'rupee' in message_lower or 'rs' in message_lower:
                    additional_entities["budget"] = f"{budget_amount} INR"
                elif 'usd' in message_lower or '$' in message_lower:
                    additional_entities["budget"] = f"{budget_amount} USD"
                else:
                    additional_entities["budget"] = budget_amount
                break

        # Extract brand patterns
        common_brands = ["apple", "dell", "hp", "lenovo", "asus", "acer", "msi", "samsung", "sony", "lg"]
        for brand in common_brands:
            if brand in message_lower:
                additional_entities["brand"] = brand.title()
                break

        return additional_entities

    def update_specifications(self, nlu_entities: Dict[str, Any], user_message: str, context_manager) -> Dict[str, Any]:
        """Update gathered specifications with enhanced entity mapping and context storage."""
        # Check if user is indicating no preference for all remaining specs
        if SpecificationSchema.detect_no_preference(user_message):
            # Mark all remaining specs as flexible/no_preference
            for spec_name in self.required_specs:
                if not self.required_specs[spec_name]:
                    self.required_specs[spec_name] = "flexible"
                    self.gathered_specs[spec_name] = "flexible"
                    context_manager.add_fact(spec_name, "flexible", "user")
            return {"all_specs_flexible": True, "missing_specs": []}

        # Map NLU entities to standard specification names
        mapped_entities = SpecificationSchema.map_entities_to_specs(nlu_entities)

        # Manual entity extraction for common cases NLU might miss
        additional_entities = self.extract_additional_entities(user_message)
        mapped_entities.update(additional_entities)

        # Update gathered specifications using mapped entities
        specs_updated = False
        for spec_name, value in mapped_entities.items():
            if spec_name in self.required_specs and value:
                self.required_specs[spec_name] = value
                self.gathered_specs[spec_name] = value
                context_manager.add_fact(spec_name, value, "user")
                specs_updated = True

        missing_specs = [spec for spec, value in self.required_specs.items() if not value]

        # If we have essential specs (use_case + budget), mark remaining as flexible
        has_essentials = self.gathered_specs.get("use_case") and self.gathered_specs.get("budget")
        if has_essentials and missing_specs:
            # Mark remaining as flexible to trigger confirmation
            for spec in missing_specs:
                self.required_specs[spec] = "flexible"
                self.gathered_specs[spec] = "flexible"
            missing_specs = []

        return {
            "specs_updated": specs_updated,
            "missing_specs": missing_specs,
            "gathered_specs": self.gathered_specs.copy()
        }

    def generate_specification_questions(self, needed_specs: List[str]) -> str:
        """Generate intelligent, business-aware questions for needed specifications using schema."""
        if not needed_specs:
            return "I need a bit more information to find the perfect solution for you."

        questions = []

        for spec in needed_specs:
            if spec == "category":
                questions.append(
                    "What type of product are you interested in? (For example: electronics, clothing, home goods)")
            elif spec == "subcategory":
                questions.append(
                    "Could you be more specific about what you need? (For example: laptop, smartphone, headphones)")
            elif spec == "use_case":
                questions.append(
                    "What will you mainly use this for? (For example: gaming, work, study, or general use)")
            elif spec == "budget":
                questions.append(
                    "What's your budget range? (For example: '50,000 INR' or 'around $800', or say 'flexible' if you're open)")
            elif spec == "brand":
                questions.append(
                    "Do you have any brand preferences or ones you'd like me to avoid? (Say 'no preference' if you're flexible)")
            elif spec == "specifications":
                questions.append(
                    "Are there any specific features or requirements that are important to you? (Or say 'no specific requirements')")
            else:
                questions.append(
                    f"Could you tell me about your {SpecificationSchema.get_spec_description(spec).lower()}? (Say 'no preference' if you're flexible)")

        if len(questions) == 1:
            return questions[0]
        elif len(questions) <= 2:
            return " ".join(questions)
        else:
            return questions[0] + " Let's start with that, and then I'll ask about the other details."

    def generate_helpful_clarification(self, missing_specs: List[str], user_message: str) -> str:
        """Generate helpful clarification when no progress is made in spec gathering."""
        if len(missing_specs) == 1:
            spec_name = missing_specs[0]
            spec_desc = SpecificationSchema.get_spec_description(spec_name)

            if spec_name == "category":
                return "I'd like to help you find the right product. Are you looking for electronics, clothing, home goods, or something else?"
            elif spec_name == "subcategory":
                return "Could you tell me specifically what type of product you need? For example: laptop, smartphone, headphones, etc.?"
            elif spec_name == "use_case":
                return "What will you mainly use this for? For example: gaming, work, study, entertainment, or general use?"
            elif spec_name == "budget":
                return "What's your budget range? You can say something like '50,000 INR' or 'around $800' or even 'flexible budget'."
            else:
                return f"Could you help me understand your {spec_desc.lower()}? If you don't have a preference, just say 'no preference'."
        else:
            return (
                "I want to find the perfect option for you. Could you help me with a few details? "
                f"I still need to know about: {', '.join(SpecificationSchema.get_spec_description(spec) for spec in missing_specs[:2])}. "
                "If you don't have preferences for any of these, just let me know!"
            )

    def create_requirement_summary(self) -> str:
        """Create a comprehensive, professional summary of gathered requirements."""
        summary_parts = []

        if self.gathered_specs.get("subcategory"):
            subcategory = self.gathered_specs["subcategory"]
            if subcategory == "flexible":
                summary_parts.append(f"**Product**: Flexible - open to recommendations")
            else:
                summary_parts.append(f"**Product**: {subcategory}")

        if self.gathered_specs.get("use_case"):
            use_case = self.gathered_specs["use_case"]
            if use_case == "flexible":
                summary_parts.append(f"**Primary Use**: Flexible - general purpose")
            else:
                summary_parts.append(f"**Primary Use**: {use_case}")

        if self.gathered_specs.get("budget"):
            budget = self.gathered_specs["budget"]
            if budget == "flexible":
                summary_parts.append(f"**Budget**: Flexible - open to various price points")
            else:
                summary_parts.append(f"**Budget**: {budget}")

        # Add other specifications with professional formatting
        other_specs = {k: v for k, v in self.gathered_specs.items()
                       if k not in ["category", "subcategory", "use_case", "budget"] and v}

        if other_specs:
            for spec_name, spec_value in other_specs.items():
                spec_display_name = SpecificationSchema.get_spec_description(spec_name)
                if spec_value == "flexible":
                    spec_strs = f"**{spec_display_name}**: Flexible - no specific preference"
                else:
                    spec_strs = f"**{spec_display_name}**: {spec_value}"
                summary_parts.append(spec_strs)

        return "Here's what I understand about your requirements:\n\n" + "\n".join(
            [f"• {part}" for part in summary_parts])

    def handle_confirmation_response(self, user_response: str, context_manager) -> Dict[str, Any]:
        """Handle user response to requirement confirmation with satisfaction detection."""
        response_lower = user_response.lower()

        # Enhanced confirmation detection with satisfaction signals
        confirmation_signals = ["yes", "correct", "that's right", "looks good", "perfect", "exactly", "right"]
        modification_signals = ["no", "not quite", "actually", "change", "also", "but", "except", "add"]
        satisfaction_signals = ["perfect", "exactly", "great", "wonderful", "excellent"]

        if any(signal in response_lower for signal in confirmation_signals):
            # User confirmed - detect satisfaction level
            satisfaction_detected = any(signal in response_lower for signal in satisfaction_signals)
            self.specs_confirmed = True
            return {"confirmed": True, "satisfaction_detected": satisfaction_detected}

        elif any(signal in response_lower for signal in modification_signals):
            # User wants to modify - gather additional info with enhanced entity extraction
            additional_entities = self.extract_additional_entities(user_response)

            # Update specifications
            for key, value in additional_entities.items():
                if value:
                    self.gathered_specs[key] = value
                    context_manager.add_fact(key, value, "user")

            return {"confirmed": False, "modifications_made": True}

        else:
            # Try to extract any additional specifications or handle ambiguity
            additional_entities = self.extract_additional_entities(user_response)

            if additional_entities:
                # Add new specifications
                for key, value in additional_entities.items():
                    if value:
                        self.gathered_specs[key] = value
                        context_manager.add_fact(key, value, "user")
                return {"confirmed": False, "modifications_made": True}
            else:
                return {"confirmed": False, "needs_clarification": True}