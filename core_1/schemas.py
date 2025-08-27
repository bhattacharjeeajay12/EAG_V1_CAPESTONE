# core_1/schemas.py
"""
Schema definitions and validation for the intelligent planner.
Handles standardized specification schemas and entity mappings.
"""

from typing import Dict, List, Any


class SpecificationSchema:
    """Standardized specification schema to prevent LLM/NLU naming mismatches."""

    # Allowed specification names (LLM must use exactly these)
    ALLOWED_SPECS = {
        "category": "Product category (electronics, clothing, etc.)",
        "subcategory": "Specific product type (laptop, smartphone, etc.)",
        "use_case": "What user will use the product for",
        "budget": "Price range or maximum budget",
        "brand": "Brand preference or requirements",
        "specifications": "Technical requirements or features"
    }

    # Entity mapping: NLU entities → Standard spec names
    ENTITY_MAPPING = {
        # Direct mappings
        "category": "category",
        "subcategory": "subcategory",
        "use_case": "use_case",
        "budget": "budget",
        "brand": "brand",
        "specifications": "specifications",

        # Alternative entity names that NLU might use
        "product_category": "category",
        "product_type": "subcategory",
        "intended_use": "use_case",
        "purpose": "use_case",
        "price_range": "budget",
        "max_budget": "budget",
        "brand_preference": "brand",
        "features": "specifications",
        "requirements": "specifications",
        "tech_specs": "specifications"
    }

    # "No preference" keywords that satisfy any specification
    NO_PREFERENCE_KEYWORDS = {
        "no preference", "no preferences", "don't care", "doesn't matter",
        "anything", "any", "flexible", "open", "not important",
        "whatever", "not picky", "no specific", "no particular"
    }

    @classmethod
    def validate_spec_names(cls, spec_list: List[str]) -> List[str]:
        """Validate and filter specification names to only allowed ones."""
        if not spec_list:
            return []

        valid_specs = []
        for spec in spec_list:
            if spec in cls.ALLOWED_SPECS:
                valid_specs.append(spec)
            else:
                # Log warning but don't break - use fallback
                print(f"⚠️ Warning: LLM requested invalid spec '{spec}', skipping")

        return valid_specs

    @classmethod
    def map_entities_to_specs(cls, entities: Dict[str, Any]) -> Dict[str, Any]:
        """Map NLU entities to standardized specification names."""
        mapped_specs = {}

        for entity_name, entity_value in entities.items():
            if entity_value:  # Only map non-empty values
                # Find the standard spec name for this entity
                standard_name = cls.ENTITY_MAPPING.get(entity_name, entity_name)
                if standard_name in cls.ALLOWED_SPECS:
                    mapped_specs[standard_name] = entity_value

        return mapped_specs

    @classmethod
    def detect_no_preference(cls, user_message: str) -> bool:
        """Detect if user is indicating no preference."""
        message_lower = user_message.lower().strip()
        return any(keyword in message_lower for keyword in cls.NO_PREFERENCE_KEYWORDS)

    @classmethod
    def get_spec_description(cls, spec_name: str) -> str:
        """Get human-readable description for a specification."""
        return cls.ALLOWED_SPECS.get(spec_name, spec_name.replace('_', ' ').title())