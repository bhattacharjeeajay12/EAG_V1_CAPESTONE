import os, json
from pydantic import BaseModel
from typing import Dict, Optional, List

# Try importing Gemini, but provide fallback if not available
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[WARN] google.generativeai package not available. Using mock extraction.")

# Define schema for structured extraction
class ReturnDetails(BaseModel):
    product_id: Optional[str] = None
    product_name: Optional[str] = None
    order_id: Optional[str] = None
    purchase_date: Optional[str] = None
    return_reason: Optional[str] = None
    condition: Optional[str] = None
    has_packaging: bool = True
    has_receipt: bool = False
    image_provided: bool = False
    image_quality: Optional[str] = None

def extract_return_details(query: str) -> ReturnDetails:
    """
    Calls Gemini to extract structured return details from a user query.
    Uses structured (JSON) output to avoid parsing errors.
    """
    if not GEMINI_AVAILABLE:
        # Fallback to simple extraction if Gemini isn't available
        return _fallback_extract(query)
    
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[WARN] GEMINI_API_KEY environment variable not set")
        return _fallback_extract(query)
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))

        prompt = f"""
You are an information extraction assistant.

Your task is to extract structured details from a user query related to returning a product.

User query: "{query}"

Return your answer in **pure JSON only** with the following structure:

- product_id (string, optional) → the ID of the product if mentioned
- product_name (string, optional) → the name of the product being returned
- order_id (string, optional) → the order identifier if mentioned
- purchase_date (string, optional) → when the product was purchased (extract any date format mentioned)
- return_reason (string, optional) → why the user wants to return (e.g., "defective", "wrong size", "changed mind")
- condition (string, optional) → the current condition of the product (e.g., "new", "used", "damaged")
- has_packaging (boolean, default=true) → whether the original packaging is available
- has_receipt (boolean, default=false) → whether the user has the receipt
- image_provided (boolean, default=false) → whether the user has provided or offered to provide images
- image_quality (string, optional) → if image is mentioned, the quality description ("good", "blurry", etc.)

⚠️ Rules:
- If a field is not mentioned, omit it (do not include null or empty strings).
- Never include text outside the JSON.
- Always return valid, parseable JSON.
"""

        response = model.generate_content(
            prompt,
            generation_config=genai.types.GenerationConfig(
                response_mime_type="application/json"
            )
        )

        try:
            details = json.loads(response.text.strip())
            return ReturnDetails(**details)
        except Exception as e:
            print("[ERROR] Could not parse Gemini response:", e)
            return _fallback_extract(query)
            
    except Exception as e:
        print("[ERROR] Gemini API call failed:", e)
        return _fallback_extract(query)

def _fallback_extract(query: str) -> ReturnDetails:
    """Simple fallback extraction when Gemini is unavailable."""
    query_lower = query.lower()
    
    # Extract product names based on common patterns
    product_name = None
    product_id = None
    return_reason = None
    
    # Common product types
    product_types = [
        "electronics", "headphones", "earphone", "shoes", "watch", "phone", 
        "laptop", "utensils", "book", "books", "sports"
    ]
    
    # Try to find product name
    for product in product_types:
        if product in query_lower:
            product_name = product
            break
    
    # Look for common return reasons
    if any(word in query_lower for word in ["broken", "not working", "defective", "damaged"]):
        return_reason = "defective"
    elif any(word in query_lower for word in ["wrong", "incorrect", "not what", "different"]):
        return_reason = "wrong item"
    elif any(word in query_lower for word in ["don't like", "don't want", "changed mind"]):
        return_reason = "changed mind"
    
    # Check for mentions of images
    has_image = any(word in query_lower for word in ["picture", "photo", "image", "sent", "attached"])
    
    return ReturnDetails(
        product_name=product_name,
        return_reason=return_reason,
        image_provided=has_image
    )

def check_return_eligibility(product_id: str, purchase_date: str, customer_id: str = None) -> Dict:
    """
    Checks if a product is eligible for return based on product_id and purchase date.
    This is a placeholder that would connect to your product database.
    """
    # This would typically query your database for the product's return window
    # For now, we'll return a mock response
    return {
        "eligible": True,
        "return_window": 15,  # days
        "days_remaining": 5,  # days remaining in return window
        "reason": "Within return window"
    }

def verify_return_image(image_data) -> Dict:
    """
    Verifies if the product image is valid for return processing.
    This is a placeholder for image analysis service.
    """
    # This would typically call an image analysis service
    # For now, we'll return a mock response
    return {
        "is_valid": True,
        "quality": "good",
        "product_visible": True,
        "damage_visible": False,
        "confidence": 0.85
    }
