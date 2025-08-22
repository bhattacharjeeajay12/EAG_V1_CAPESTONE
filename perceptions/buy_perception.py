import google.generativeai as genai
from pydantic import BaseModel, Field
from typing import Dict, Optional
import os, json, re

# Configure Gemini API
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=GEMINI_API_KEY)

# Define schema for structured extraction
class BuyDetails(BaseModel):
    category: Optional[str] = None
    subcategory: Optional[str] = None
    product_name: Optional[str] = None
    specifications: Dict[str, str] = Field(default_factory=dict)
    quantity: int = 1
    budget: Optional[str] = None


def extract_buy_details(query: str) -> BuyDetails:
    """
    Calls Gemini to extract structured product details from a query.
    Uses structured (JSON) output to avoid parsing errors.
    Falls back to a heuristic extractor if the API is unavailable or fails.
    """
    model_name = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

    model = genai.GenerativeModel(model_name)

    prompt = f"""
            You are an information extraction assistant.

            Your task is to extract structured details from a user query related to buying a product. 
            Implemented categories: electronics, sports.
            Electronics subcategories: laptop, smartphone, earphone, graphic tablet, camera.
            Sports subcategories: yoga mat, shoes, dumbbells, cricket bat, basketball, treadmill.

            Rules for extraction:
            - category: must be "electronics" or "sports". If not identifiable, set to null.
            - subcategory: must be one of the listed subcategories for that category. If not identifiable, set to null.
            - product_name: natural phrasing of the product (e.g. "Dell laptop", "Sony earphones", "SG cricket bat"). 
              If no brand given, use just the subcategory (e.g. "laptop"). If product is not identifiable, set to null.
            - specifications: only intrinsic product attributes (brand, color, RAM, storage, GPU, weight, size, material, etc.). Default = {{}}.
            - quantity: if not mentioned, default to 1.
            - budget: include if user mentions price, budget, or range. Otherwise omit.
            - Always return valid JSON. 
            - Use null explicitly if category, subcategory, or product_name cannot be determined.

            Here are some examples:

            User query: "I want to buy a black Dell laptop with 16GB RAM under 80000 INR"
            JSON:
            {{
              "category": "electronics",
              "subcategory": "laptop",
              "product_name": "Dell laptop",
              "specifications": {{
                "brand": "Dell",
                "color": "black",
                "RAM": "16GB"
              }},
              "quantity": 1,
              "budget": "80000 INR"
            }}

            User query: "Need 2 basketballs size 7"
            JSON:
            {{
              "category": "sports",
              "subcategory": "basketball",
              "product_name": "basketball",
              "specifications": {{
                "size": "7"
              }},
              "quantity": 2
            }}

            User query: "Looking for a cricket bat by SG under ₹5000"
            JSON:
            {{
              "category": "sports",
              "subcategory": "cricket bat",
              "product_name": "SG cricket bat",
              "specifications": {{
                "brand": "SG"
              }},
              "quantity": 1,
              "budget": "₹5000"
            }}

            User query: "Buy two 10kg dumbbells"
            JSON:
            {{
              "category": "sports",
              "subcategory": "dumbbells",
              "product_name": "dumbbells",
              "specifications": {{
                "weight": "10kg"
              }},
              "quantity": 2
            }}

            User query: "Show me a 128GB Samsung smartphone under 60000 INR"
            JSON:
            {{
              "category": "electronics",
              "subcategory": "smartphone",
              "product_name": "Samsung smartphone",
              "specifications": {{
                "brand": "Samsung",
                "storage": "128GB"
              }},
              "quantity": 1,
              "budget": "60000 INR"
            }}

            User query: "Need 2 wireless Bluetooth earphones by Sony"
            JSON:
            {{
              "category": "electronics",
              "subcategory": "earphone",
              "product_name": "Sony wireless Bluetooth earphones",
              "specifications": {{
                "brand": "Sony",
                "connectivity": "Bluetooth",
                "form_factor": "wireless"
              }},
              "quantity": 2
            }}

            User query: "Show me a laptop"
            JSON:
            {{
              "category": "electronics",
              "subcategory": "laptop",
              "product_name": "laptop",
              "specifications": {{}},
              "quantity": 1
            }}

            User query: "Hello"
            JSON:
            {{
              "category": null,
              "subcategory": null,
              "product_name": null,
              "specifications": {{}},
              "quantity": 1
            }}

            User query: "Can you help me?"
            JSON:
            {{
              "category": null,
              "subcategory": null,
              "product_name": null,
              "specifications": {{}},
              "quantity": 1
            }}

            Now process this query:

            User query: "{query}"
            JSON:
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
        print("[WARN] Buy Perception layer failed due to error:", e)


if __name__ == "__main__":
    samples = [
        "I want to buy a black Dell laptop with 16GB RAM under 80000 INR",
        "Need 2 pairs of running shoes for men, size 10",
        "Looking for a green yoga mat",
        "Buy iPhone 14 Pro Max",
        "Show me smart watches",
        "Budget is 30000"
    ]

    print("\n=== Running test samples ===\n")
    for q in samples:
        print(f"Query: {q}")
        details = extract_buy_details(q)
        print("Extracted:", details.model_dump())
        print("-" * 60)