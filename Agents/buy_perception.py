import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import Dict, Optional
import os, json, re

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Define schema for structured extraction
class BuyDetails(BaseModel):
    product_name: str
    specifications: Dict[str, str] = Field(default_factory=dict)  # matches your DB schema
    quantity: int = 1
    budget: Optional[str] = None
    category: Optional[str] = None


def _heuristic_extract(query: str) -> BuyDetails:
    """A lightweight fallback extractor used when Gemini is unavailable or fails."""
    q_lower = query.lower()
    # Quantity: simple number detection
    qty_match = re.search(r"\b(\d+)\b", q_lower)
    quantity = int(qty_match.group(1)) if qty_match else 1

    # Budget: look for patterns like $100, 100 usd, 5000 inr, under 100
    budget = None
    currency_match = re.search(r"(?:rs\.?|inr|usd|\$|₹)\s*([0-9]+(?:,[0-9]{3})*(?:\.[0-9]+)?)", q_lower)
    if currency_match:
        budget = currency_match.group(0)
    else:
        under_match = re.search(r"(?:under|below|less than)\s*([0-9]+)", q_lower)
        if under_match:
            budget = under_match.group(0)

    # Category keywords (very rough)
    category = None
    for cat in ["electronics", "books", "sports", "fashion", "clothing", "shoes", "utensils", "home", "grocery", "toys"]:
        if cat in q_lower:
            category = cat
            break

    # Product name: capture words after intent verbs
    product_name = "unknown"
    intent_match = re.search(r"\b(?:need|want|buy|looking for|searching for|get me|show me)\b\s+(.+)", q_lower)
    if intent_match:
        product_name = intent_match.group(1).strip().rstrip(".?!")
    else:
        # fallback: take the query minus politeness
        product_name = re.sub(r"^(hi|hello|hey)[,\s]+", "", q_lower).strip().rstrip(".?!")

    # Very naive spec extraction: colors and gender/age hints
    specifications: Dict[str, str] = {}
    colors = ["black", "white", "red", "blue", "green", "yellow", "pink", "purple", "grey", "gray", "brown", "orange"]
    for c in colors:
        if re.search(rf"\b{re.escape(c)}\b", q_lower):
            specifications["color"] = c
            break
    if "male" in q_lower or "men" in q_lower or "man" in q_lower:
        specifications["gender"] = "men"
    if "female" in q_lower or "women" in q_lower or "woman" in q_lower:
        specifications["gender"] = "women"
    size_match = re.search(r"\bsize\s*(\w+)\b", q_lower)
    if size_match:
        specifications["size"] = size_match.group(1)
    brand_match = re.search(r"\bby\s+([a-z0-9\- ]{2,})\b", q_lower)
    if brand_match:
        specifications["brand"] = brand_match.group(1).strip()

    return BuyDetails(
        product_name=product_name,
        specifications=specifications,
        quantity=quantity,
        budget=budget,
        category=category,
    )


def extract_buy_details(query: str) -> BuyDetails:
    """
    Calls Gemini to extract structured product details from a query.
    Uses structured (JSON) output to avoid parsing errors.
    Falls back to a heuristic extractor if the API is unavailable or fails.
    """
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    if not GEMINI_API_KEY:
        # No API key; use fallback
        return _heuristic_extract(query)

    model = genai.GenerativeModel(model_name)

    prompt = f"""
You are an information extraction assistant.

Your task is to extract structured details from a user query related to buying a product.

User query: "{query}"

Return your answer in pure JSON only with the following structure:

- product_name (string, required) → the main product the user wants
- specifications (object, optional) → only the intrinsic product attributes such as:
  - color
  - size
  - gender
  - age_group
  - brand
  - material
  - model
  - any other descriptive features of the product itself
- quantity (integer, default = 1 if not provided) → how many units the user wants
- budget (string or number, optional) → the budget or price range mentioned by the user (e.g., "80000 INR", "<50 USD")
- category (string, optional) → high-level product category such as "electronics", "books", "sports", "utensils"

Rules:
- The response must be a single valid JSON object and nothing else.
- `specifications` must include only product attributes (do NOT include quantity, budget, or category).
- If a field is not mentioned, omit it (do not include null or empty strings).
- Always return valid, parseable JSON.
"""

    try:
        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )
        details = json.loads(response.text.strip())
        return BuyDetails(**details)
    except Exception as e:
        print("[WARN] Falling back to heuristic extractor due to error:", e)
        return _heuristic_extract(query)
