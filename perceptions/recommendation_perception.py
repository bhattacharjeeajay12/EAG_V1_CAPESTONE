import os, json
from pydantic import BaseModel
from typing import Dict, List, Optional, Union, Any

# Try importing Gemini, but provide fallback if not available
try:
    import google.generativeai as genai
    GEMINI_AVAILABLE = True
except ImportError:
    GEMINI_AVAILABLE = False
    print("[WARN] google.generativeai package not available. Using mock extraction.")

# Define schema for recommendation input
class UserPreference(BaseModel):
    """Captures user preferences and constraints for recommendations."""
    category: Optional[str] = None
    product_type: Optional[str] = None
    price_range: Optional[Dict[str, float]] = None  # {"min": 10.0, "max": 50.0}
    brand_preferences: List[str] = []
    features: List[str] = []
    constraints: List[str] = []
    past_purchases: List[str] = []
    search_query: Optional[str] = None
    user_id: Optional[str] = None

# Define schema for product data
class Product(BaseModel):
    """Represents a product that can be recommended."""
    product_id: str
    product_name: str
    category_id: int
    category: Optional[str] = None
    price: float
    items_included: Optional[str] = None
    product_description: Optional[str] = None
    return_window: int
    in_stock: bool = True
    features: List[str] = []
    rating: Optional[float] = None
    review_count: Optional[int] = None

# Define schema for recommendation output
class Recommendation(BaseModel):
    """A single product recommendation with reasoning."""
    product: Product
    relevance_score: float
    reasoning: str

class RecommendationResponse(BaseModel):
    """Complete recommendation response."""
    recommendations: List[Recommendation]
    filtering_criteria: Dict[str, Any]
    query_understanding: str

def extract_user_preferences(query: str) -> UserPreference:
    """
    Extracts user preferences and constraints from a natural language query.
    """
    if not GEMINI_AVAILABLE:
        # Fallback to simple extraction if Gemini isn't available
        return _fallback_extract_preferences(query)

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("[WARN] GEMINI_API_KEY environment variable not set")
        return _fallback_extract_preferences(query)

    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel(os.getenv("GEMINI_MODEL", "gemini-1.5-flash"))

        prompt = f"""
You are an information extraction assistant for an e-commerce recommendation system.

Your task is to extract structured preference details from a user query.

User query: "{query}"

Return your answer in **pure JSON only** with the following structure:

- category (string, optional) → product category (e.g., "electronics", "books")
- product_type (string, optional) → specific type of product (e.g., "headphones", "mystery novel")
- price_range (object, optional) → min and max price values, if mentioned (e.g., {{"min": 20, "max": 50}})
- brand_preferences (array of strings) → preferred brands, if any
- features (array of strings) → desired product features or attributes
- constraints (array of strings) → limitations or requirements
- past_purchases (array of strings) → previously bought items mentioned in the query
- search_query (string, optional) → the core search intention

⚠️ Rules:
- If a field is not mentioned, use null or empty array as appropriate.
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
            return UserPreference(**details)
        except Exception as e:
            print("[ERROR] Could not parse Gemini response:", e)
            return _fallback_extract_preferences(query)

    except Exception as e:
        print("[ERROR] Gemini API call failed:", e)
        return _fallback_extract_preferences(query)

def _fallback_extract_preferences(query: str) -> UserPreference:
    """Simple fallback extraction when Gemini is unavailable."""
    query_lower = query.lower()

    # Initialize preferences
    preferences = UserPreference()

    # Extract category
    categories = ["electronics", "books", "sports", "utensils", "clothing", "shoes"]
    for category in categories:
        if category in query_lower:
            preferences.category = category
            break

    # Extract product types
    product_types = {
        "electronics": ["headphones", "earphones", "laptop", "phone", "television", "camera"],
        "books": ["novel", "textbook", "fiction", "non-fiction", "biography"],
        "sports": ["shoes", "equipment", "clothing"],
        "clothing": ["shirt", "pants", "dress", "jacket"]
    }

    if preferences.category and preferences.category in product_types:
        for product_type in product_types[preferences.category]:
            if product_type in query_lower:
                preferences.product_type = product_type
                break

    # Extract price range
    price_indicators = ["under", "below", "above", "over", "between", "less than", "more than", "around"]
    for indicator in price_indicators:
        if indicator in query_lower:
            # Simple extraction - not robust for real use
            if "under" in query_lower or "below" in query_lower or "less than" in query_lower:
                import re
                amounts = re.findall(r'\d+', query)
                if amounts:
                    preferences.price_range = {"min": 0, "max": float(amounts[0])}
            elif "above" in query_lower or "over" in query_lower or "more than" in query_lower:
                import re
                amounts = re.findall(r'\d+', query)
                if amounts:
                    preferences.price_range = {"min": float(amounts[0]), "max": 1000000}
            elif "between" in query_lower:
                import re
                amounts = re.findall(r'\d+', query)
                if len(amounts) >= 2:
                    preferences.price_range = {"min": float(amounts[0]), "max": float(amounts[1])}
            break

    # Extract features
    feature_keywords = ["wireless", "wired", "bluetooth", "waterproof", "noise-cancelling", 
                        "portable", "lightweight", "durable", "fast", "premium"]
    preferences.features = [feature for feature in feature_keywords if feature in query_lower]

    # Extract brand preferences
    brands = ["sony", "apple", "samsung", "bose", "amazon", "google", "microsoft", "nike", "adidas"]
    preferences.brand_preferences = [brand for brand in brands if brand in query_lower]

    # Set search query
    preferences.search_query = query

    return preferences

def load_product_data(data_path: Optional[str] = None) -> List[Product]:
    """
    Loads product data from CSV or JSON file.
    Returns a list of Product objects.
    """
    import csv
    from pathlib import Path

    if data_path is None:
        # Look for product.json in common locations
        possible_paths = [
            "product.json",
            "../product.json",
            "Data/product.json",
            "../Data/product.json",
        ]

        for path in possible_paths:
            if Path(path).exists():
                data_path = path
                break

    if not data_path or not Path(data_path).exists():
        print("[WARN] Product data file not found. Using sample data.")
        # Return some sample products
        return [
            Product(
                product_id="100",
                product_name="Premium Wireless Headphones",
                category_id=1,
                category="Electronics",
                price=129.99,
                items_included="Headphones, charging cable, case",
                product_description="High-quality wireless headphones with noise cancellation",
                return_window=30,
                in_stock=True,
                features=["wireless", "noise-cancelling", "bluetooth"],
                rating=4.5,
                review_count=230
            ),
            Product(
                product_id="101",
                product_name="Budget Wired Earphones",
                category_id=1,
                category="Electronics",
                price=19.99,
                items_included="Earphones, extra ear tips",
                product_description="Affordable wired earphones with good sound quality",
                return_window=15,
                in_stock=True,
                features=["wired", "lightweight"],
                rating=4.0,
                review_count=185
            ),
            Product(
                product_id="102",
                product_name="Smartphone Holder",
                category_id=1,
                category="Electronics",
                price=15.99,
                items_included="Holder, adhesive pad",
                product_description="Adjustable smartphone holder for car or desk",
                return_window=30,
                in_stock=True,
                features=["adjustable", "portable"],
                rating=4.2,
                review_count=95
            )
        ]

    try:
        products = []
        if data_path.endswith('.csv'):
            with open(data_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Convert price from string to float
                    if 'price' in row:
                        row['price'] = float(row['price'])

                    # Convert category_id from string to int
                    if 'category_id' in row:
                        row['category_id'] = int(row['category_id'])

                    # Convert return_window from string to int
                    if 'return_window' in row:
                        row['return_window'] = int(row['return_window'])

                    # Add category name based on category_id
                    category_map = {
                        1: "Electronics",
                        2: "Utensils",
                        3: "Books",
                        4: "Sports"
                    }
                    if 'category_id' in row and row['category_id'] in category_map:
                        row['category'] = category_map[row['category_id']]

                    # Add in_stock (all products assumed in stock for this example)
                    row['in_stock'] = True

                    # Extract features from product description
                    if 'product_description' in row:
                        # For this example, just use some random words from the description as features
                        words = row['product_description'].lower().split()
                        features = []
                        feature_keywords = ["wireless", "wired", "bluetooth", "waterproof", "portable", 
                                            "lightweight", "durable", "fast", "premium", "quality"]
                        for keyword in feature_keywords:
                            if keyword in words:
                                features.append(keyword)
                        row['features'] = features
                    else:
                        row['features'] = []

                    # Create Product object
                    products.append(Product(**row))

        elif data_path.endswith('.json'):
            with open(data_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for item in data:
                    products.append(Product(**item))

        return products
    except Exception as e:
        print(f"[ERROR] Failed to load product data: {e}")
        return []

def rank_products(preferences: UserPreference, products: List[Product]) -> List[Recommendation]:
    """
    Ranks products based on user preferences.
    Returns a list of Recommendation objects sorted by relevance score.
    """
    recommendations = []

    for product in products:
        score = 0.0
        reasoning = []

        # Category match
        if preferences.category and product.category and preferences.category.lower() == product.category.lower():
            score += 30.0
            reasoning.append(f"Matches your preferred category: {product.category}")

        # Product type match
        if preferences.product_type:
            product_terms = set(product.product_name.lower().split() + 
                              (product.product_description.lower().split() if product.product_description else []))
            if preferences.product_type.lower() in product_terms:
                score += 25.0
                reasoning.append(f"This is a {preferences.product_type} as requested")

        # Price range match
        if preferences.price_range:
            if (not preferences.price_range.get("min") or product.price >= preferences.price_range["min"]) and \
               (not preferences.price_range.get("max") or product.price <= preferences.price_range["max"]):
                score += 20.0
                if preferences.price_range.get("min") and preferences.price_range.get("max"):
                    reasoning.append(f"Price (${product.price:.2f}) is within your budget range (${preferences.price_range['min']:.2f} - ${preferences.price_range['max']:.2f})")
                elif preferences.price_range.get("max"):
                    reasoning.append(f"Price (${product.price:.2f}) is below your maximum budget of ${preferences.price_range['max']:.2f}")
                elif preferences.price_range.get("min"):
                    reasoning.append(f"Price (${product.price:.2f}) meets your minimum quality threshold of ${preferences.price_range['min']:.2f}")

        # Brand match
        if preferences.brand_preferences:
            for brand in preferences.brand_preferences:
                if brand.lower() in product.product_name.lower():
                    score += 15.0
                    reasoning.append(f"Made by {brand.title()}, one of your preferred brands")
                    break

        # Feature match
        if preferences.features and product.features:
            matching_features = set(f.lower() for f in preferences.features) & set(f.lower() for f in product.features)
            score += len(matching_features) * 10.0
            if matching_features:
                reasoning.append(f"Has requested features: {', '.join(matching_features)}")

        # Add some randomness to break ties
        import random
        score += random.uniform(0, 5)

        if score > 0:
            recommendation = Recommendation(
                product=product,
                relevance_score=score,
                reasoning=". ".join(reasoning) if reasoning else "Matches general search criteria"
            )
            recommendations.append(recommendation)

    # Sort by relevance score (descending)
    recommendations.sort(key=lambda x: x.relevance_score, reverse=True)

    return recommendations

def get_recommendations(query: str, product_data_path: Optional[str] = None) -> RecommendationResponse:
    """
    Main function to generate recommendations based on a user query.
    """
    # Extract user preferences
    preferences = extract_user_preferences(query)

    # Load product data
    products = load_product_data(product_data_path)

    # Rank products
    ranked_recommendations = rank_products(preferences, products)

    # Build response
    response = RecommendationResponse(
        recommendations=ranked_recommendations[:5],  # Top 5 recommendations
        filtering_criteria={
            "category": preferences.category,
            "product_type": preferences.product_type,
            "price_range": preferences.price_range,
            "features": preferences.features,
            "brands": preferences.brand_preferences
        },
        query_understanding=f"You're looking for {preferences.product_type or 'products'}" + 
                           (f" in the {preferences.category} category" if preferences.category else "") +
                           (f" with features: {', '.join(preferences.features)}" if preferences.features else "")
    )

    return response
