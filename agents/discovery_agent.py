# core/discovery_agent.py
"""
Discovery Agent - Dual-Mode Product Discovery Engine

Purpose: Intelligent product discovery that adapts based on user specificity:
- Specific users: Search-first, then recommendations
- Vague users: Recommend-first, then search refinement

Key Features:
- Dual-mode operation (search-first vs recommend-first)
- Category-specific specification handling
- Smart requirement gathering and validation
- Integration with recommendation engine backend
- Seamless search and recommendation blending
"""

from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class DiscoveryMode(Enum):
    """Discovery modes based on user specificity."""
    SEARCH_FIRST = "search_first"  # User has specific requirements
    RECOMMEND_FIRST = "recommend_first"  # User is vague/needs guidance


class UserSpecificity(Enum):
    """User specificity levels."""
    SPECIFIC = "specific"  # Clear requirements
    MODERATE = "moderate"  # Some requirements
    VAGUE = "vague"  # Needs guidance


@dataclass
class DiscoveryRequest:
    """Structured discovery request with user requirements."""
    category: str
    subcategory: str
    specifications: Dict[str, Any]
    budget: Optional[str] = None
    user_specificity: UserSpecificity = UserSpecificity.MODERATE
    discovery_mode: DiscoveryMode = DiscoveryMode.SEARCH_FIRST
    preferences: List[str] = None
    use_case: Optional[str] = None


@dataclass
class DiscoveryResult:
    """Discovery result with search and recommendation data."""
    status: str
    discovery_mode: DiscoveryMode
    search_results: List[Dict[str, Any]]
    recommendations: List[Dict[str, Any]]
    total_found: int
    user_message: str
    next_actions: List[str]
    refinement_suggestions: List[str] = None


class DiscoveryAgent:
    """
    Dual-mode discovery agent that adapts to user specificity.
    """

    def __init__(self, mock_product_db: List[Dict[str, Any]] = None):
        """Initialize Discovery Agent with product database."""
        self.product_db = mock_product_db or []
        self.category_specs = self._initialize_category_specifications()

    def discover_products(self, request: DiscoveryRequest) -> DiscoveryResult:
        """
        Main discovery method - routes to appropriate mode.

        Args:
            request: Structured discovery request

        Returns:
            DiscoveryResult with products and recommendations
        """
        try:
            if request.discovery_mode == DiscoveryMode.SEARCH_FIRST:
                return self._search_first_discovery(request)
            else:
                return self._recommend_first_discovery(request)

        except Exception as e:
            return self._create_error_result(f"Discovery failed: {str(e)}", request)

    def determine_user_specificity(self, user_requirements: Dict[str, Any],
                                   user_message: str) -> Tuple[UserSpecificity, DiscoveryMode]:
        """
        Analyze user specificity to determine discovery mode.

        Args:
            user_requirements: Extracted user requirements
            user_message: Original user message

        Returns:
            Tuple of (UserSpecificity, DiscoveryMode)
        """
        specificity_score = 0

        # Check for specific requirements
        if user_requirements.get("specifications"):
            specificity_score += len(user_requirements["specifications"])

        if user_requirements.get("budget"):
            specificity_score += 1

        # Check message for specific indicators
        specific_indicators = ["show me", "find", "with", "having", "rtx", "16gb", "ssd", "15 inch"]
        vague_indicators = ["good", "best", "recommend", "suggest", "help me choose", "don't know"]

        message_lower = user_message.lower()

        for indicator in specific_indicators:
            if indicator in message_lower:
                specificity_score += 1

        for indicator in vague_indicators:
            if indicator in message_lower:
                specificity_score -= 1

        # Determine specificity level
        if specificity_score >= 3:
            return UserSpecificity.SPECIFIC, DiscoveryMode.SEARCH_FIRST
        elif specificity_score <= 0:
            return UserSpecificity.VAGUE, DiscoveryMode.RECOMMEND_FIRST
        else:
            return UserSpecificity.MODERATE, DiscoveryMode.SEARCH_FIRST

    def _search_first_discovery(self, request: DiscoveryRequest) -> DiscoveryResult:
        """
        Search-first mode: Find matching products, then highlight recommendations.
        """
        # Step 1: Search products based on specifications
        search_results = self._search_products(request)

        if not search_results:
            return self._handle_no_results(request)

        # Step 2: Generate recommendations from search results
        recommendations = self._generate_recommendations_from_search(search_results, request)

        # Step 3: Create user-friendly message
        user_message = self._create_search_first_message(search_results, recommendations, request)

        return DiscoveryResult(
            status="success",
            discovery_mode=DiscoveryMode.SEARCH_FIRST,
            search_results=search_results,
            recommendations=recommendations,
            total_found=len(search_results),
            user_message=user_message,
            next_actions=["see_more_details", "refine_search", "get_recommendations"],
            refinement_suggestions=self._get_refinement_suggestions(request, search_results)
        )

    def _recommend_first_discovery(self, request: DiscoveryRequest) -> DiscoveryResult:
        """
        Recommend-first mode: Show top recommendations, then offer search.
        """
        # Step 1: Generate smart recommendations based on requirements
        recommendations = self._generate_smart_recommendations(request)

        if not recommendations:
            return self._handle_no_recommendations(request)

        # Step 2: Find broader search results for exploration
        search_results = self._search_products(request, broad_search=True)

        # Step 3: Create user-friendly message
        user_message = self._create_recommend_first_message(recommendations, request)

        return DiscoveryResult(
            status="success",
            discovery_mode=DiscoveryMode.RECOMMEND_FIRST,
            search_results=search_results,
            recommendations=recommendations,
            total_found=len(search_results),
            user_message=user_message,
            next_actions=["see_details", "explore_more_options", "refine_needs"],
            refinement_suggestions=self._get_recommendation_refinements(request)
        )

    def _search_products(self, request: DiscoveryRequest, broad_search: bool = False) -> List[Dict[str, Any]]:
        """Search products based on request criteria."""
        matching_products = []

        for product in self.product_db:
            score = 0

            # Category matching (required)
            if request.category.lower() in product.get("category", "").lower():
                score += 3
            if request.subcategory.lower() in product.get("subcategory", "").lower():
                score += 3

            if score < 3:  # Must match category/subcategory
                continue

            # Specification matching
            if request.specifications:
                product_specs = product.get("specifications", [])
                spec_text = " ".join(product_specs).lower()

                for spec_key, spec_value in request.specifications.items():
                    if isinstance(spec_value, str) and spec_value.lower() in spec_text:
                        score += 2
                    elif isinstance(spec_value, list):
                        for val in spec_value:
                            if str(val).lower() in spec_text:
                                score += 1

            # Budget filtering
            if request.budget and not broad_search:
                budget_limit = self._extract_budget_limit(request.budget)
                if budget_limit and product.get("price", 0) > budget_limit:
                    continue

            if score > 0:
                product_copy = product.copy()
                product_copy["match_score"] = score
                matching_products.append(product_copy)

        # Sort by match score and rating
        matching_products.sort(key=lambda x: (x["match_score"], x.get("rating", 0)), reverse=True)

        # Return top results (more for broad search)
        limit = 10 if broad_search else 6
        return matching_products[:limit]

    def _generate_recommendations_from_search(self, search_results: List[Dict[str, Any]],
                                              request: DiscoveryRequest) -> List[Dict[str, Any]]:
        """Generate recommendations by highlighting best options from search results."""
        if not search_results:
            return []

        # Score products based on rating, reviews, and match quality
        for product in search_results:
            rec_score = 0
            rec_score += product.get("rating", 0) * 10  # Rating weight
            rec_score += product.get("match_score", 0) * 5  # Match weight

            # Boost popular products
            if product.get("rating", 0) >= 4.5:
                rec_score += 5

            product["recommendation_score"] = rec_score
            product["recommendation_reason"] = self._generate_recommendation_reason(product, request)

        # Sort by recommendation score
        search_results.sort(key=lambda x: x.get("recommendation_score", 0), reverse=True)

        # Return top 3 as recommendations
        return search_results[:3]

    def _generate_smart_recommendations(self, request: DiscoveryRequest) -> List[Dict[str, Any]]:
        """Generate intelligent recommendations based on use case and requirements."""
        # Get all products in category
        category_products = [
            p for p in self.product_db
            if request.category.lower() in p.get("category", "").lower()
               and request.subcategory.lower() in p.get("subcategory", "").lower()
        ]

        if not category_products:
            return []

        # Score products for recommendation
        for product in category_products:
            rec_score = 0

            # Base score from rating
            rec_score += product.get("rating", 0) * 10

            # Use case matching
            if request.use_case:
                use_case_lower = request.use_case.lower()
                product_specs = " ".join(product.get("specifications", [])).lower()

                if "gaming" in use_case_lower and any(spec in product_specs for spec in ["rtx", "gaming", "nvidia"]):
                    rec_score += 15
                elif "business" in use_case_lower and any(
                        spec in product_specs for spec in ["professional", "security", "lightweight"]):
                    rec_score += 15
                elif "photography" in use_case_lower and any(
                        spec in product_specs for spec in ["camera", "display", "color"]):
                    rec_score += 15

            # Budget consideration
            if request.budget:
                budget_limit = self._extract_budget_limit(request.budget)
                if budget_limit:
                    if product.get("price", 0) <= budget_limit:
                        rec_score += 10  # Bonus for within budget
                    elif product.get("price", 0) > budget_limit * 1.2:
                        rec_score -= 20  # Penalty for too expensive

            product["recommendation_score"] = rec_score
            product["recommendation_reason"] = self._generate_recommendation_reason(product, request)

        # Sort and return top recommendations
        category_products.sort(key=lambda x: x.get("recommendation_score", 0), reverse=True)
        return category_products[:3]

    def _generate_recommendation_reason(self, product: Dict[str, Any],
                                        request: DiscoveryRequest) -> str:
        """Generate human-readable recommendation reasoning."""
        reasons = []

        # Rating-based reason
        rating = product.get("rating", 0)
        if rating >= 4.7:
            reasons.append("highly rated")
        elif rating >= 4.5:
            reasons.append("excellent reviews")
        elif rating >= 4.0:
            reasons.append("good ratings")

        # Spec-based reasons
        specs = product.get("specifications", [])
        if request.use_case:
            use_case_lower = request.use_case.lower()
            if "gaming" in use_case_lower and any("gaming" in spec or "rtx" in spec for spec in specs):
                reasons.append("great for gaming")
            elif "business" in use_case_lower and any("professional" in spec for spec in specs):
                reasons.append("perfect for business")

        # Budget-based reason
        if request.budget:
            budget_limit = self._extract_budget_limit(request.budget)
            if budget_limit and product.get("price", 0) <= budget_limit * 0.8:
                reasons.append("great value")

        return ", ".join(reasons) if reasons else "matches your needs"

    def _create_search_first_message(self, search_results: List[Dict[str, Any]],
                                     recommendations: List[Dict[str, Any]],
                                     request: DiscoveryRequest) -> str:
        """Create user message for search-first mode."""

        total_count = len(search_results)

        if total_count == 0:
            return "I couldn't find products matching your exact specifications. Let me show you some alternatives."

        # Main search results message
        message = f"I found {total_count} {request.subcategory}s matching your specifications:\n\n"

        # Show first few results
        for i, product in enumerate(search_results[:3], 1):
            message += f"{i}. {product['name']} - ${product['price']} ({product.get('rating', 'N/A')}/5 stars)\n"

        # Highlight recommendations
        if recommendations and len(recommendations) > 0:
            message += f"\n⭐ Based on reviews and ratings, I especially recommend:\n"
            top_rec = recommendations[0]
            reason = top_rec.get("recommendation_reason", "highly rated")
            message += f"• {top_rec['name']} - {reason}\n"

        message += f"\nWould you like details on any of these, or shall I refine the search?"

        return message

    def _create_recommend_first_message(self, recommendations: List[Dict[str, Any]],
                                        request: DiscoveryRequest) -> str:
        """Create user message for recommend-first mode."""

        if not recommendations:
            return f"I need a bit more information to recommend the best {request.subcategory} for you. What will you mainly use it for?"

        message = f"Here are my top recommendations for {request.subcategory}:\n\n"

        for i, rec in enumerate(recommendations, 1):
            reason = rec.get("recommendation_reason", "great choice")
            message += f"{i}. {rec['name']} - ${rec['price']}\n"
            message += f"   ⭐ {rec.get('rating', 'N/A')}/5 stars - {reason}\n\n"

        message += "Would you like more details about any of these, or want to see more options?"

        return message

    def _handle_no_results(self, request: DiscoveryRequest) -> DiscoveryResult:
        """Handle case when no products match search criteria."""

        # Try broader search
        broad_results = self._search_products(request, broad_search=True)

        if broad_results:
            message = (f"No products match your exact specifications, but here are some "
                       f"{request.subcategory}s you might consider:\n\n")

            for i, product in enumerate(broad_results[:3], 1):
                message += f"{i}. {product['name']} - ${product['price']}\n"

            message += "\nWould you like to adjust your requirements?"

            return DiscoveryResult(
                status="partial_results",
                discovery_mode=request.discovery_mode,
                search_results=broad_results,
                recommendations=[],
                total_found=len(broad_results),
                user_message=message,
                next_actions=["adjust_requirements", "see_alternatives"],
                refinement_suggestions=["Consider higher budget", "Try different specifications"]
            )
        else:
            return DiscoveryResult(
                status="no_results",
                discovery_mode=request.discovery_mode,
                search_results=[],
                recommendations=[],
                total_found=0,
                user_message=f"I couldn't find any {request.subcategory}s in our catalog. Could you try a different product category?",
                next_actions=["try_different_category", "contact_support"]
            )

    def _handle_no_recommendations(self, request: DiscoveryRequest) -> DiscoveryResult:
        """Handle case when no recommendations can be generated."""

        return DiscoveryResult(
            status="insufficient_data",
            discovery_mode=request.discovery_mode,
            search_results=[],
            recommendations=[],
            total_found=0,
            user_message=f"I need more information about your needs to recommend the best {request.subcategory}. What will you mainly use it for?",
            next_actions=["provide_use_case", "specify_requirements"]
        )

    def _get_refinement_suggestions(self, request: DiscoveryRequest,
                                    results: List[Dict[str, Any]]) -> List[str]:
        """Get suggestions for search refinement."""
        suggestions = []

        if request.budget:
            suggestions.append("Adjust budget range")

        if len(results) > 10:
            suggestions.append("Add more specific requirements")
        elif len(results) < 3:
            suggestions.append("Broaden requirements")

        suggestions.extend(["Filter by brand", "Sort by price", "See customer reviews"])

        return suggestions

    def _get_recommendation_refinements(self, request: DiscoveryRequest) -> List[str]:
        """Get suggestions for recommendation refinement."""
        return [
            "Tell me your main use case",
            "Specify budget preference",
            "Mention important features",
            "Share brand preferences"
        ]

    def _extract_budget_limit(self, budget_str: str) -> Optional[int]:
        """Extract numeric budget limit from budget string."""
        if not budget_str:
            return None

        import re
        numbers = re.findall(r'\d+', budget_str)
        if numbers:
            return int(numbers[0])
        return None

    def _initialize_category_specifications(self) -> Dict[str, List[str]]:
        """Initialize category-specific specifications."""
        return {
            "laptop": ["ram", "storage", "graphics", "screen_size", "processor", "brand", "weight"],
            "smartphone": ["camera", "storage", "battery", "screen_size", "brand", "5g"],
            "headphones": ["noise_cancelling", "wireless", "battery_life", "brand", "type"],
            "tablet": ["screen_size", "storage", "battery_life", "brand", "stylus_support"]
        }

    def _create_error_result(self, error_message: str, request: DiscoveryRequest) -> DiscoveryResult:
        """Create error result for discovery failures."""
        return DiscoveryResult(
            status="error",
            discovery_mode=request.discovery_mode,
            search_results=[],
            recommendations=[],
            total_found=0,
            user_message="I encountered an issue while searching. Let me try a different approach.",
            next_actions=["try_again", "simplify_request"],
            refinement_suggestions=[]
        )


def test_discovery_agent():
    """Test Discovery Agent with various scenarios."""
    print("🧪 Testing Discovery Agent")
    print("=" * 60)

    # Sample product database
    sample_products = [
        {
            "id": "laptop_001",
            "name": "Dell Gaming Laptop G15",
            "category": "electronics",
            "subcategory": "laptop",
            "price": 1299,
            "brand": "Dell",
            "specifications": ["gaming", "nvidia_rtx", "16gb_ram", "ssd"],
            "rating": 4.5
        },
        {
            "id": "laptop_002",
            "name": "MacBook Pro M3",
            "category": "electronics",
            "subcategory": "laptop",
            "price": 1999,
            "brand": "Apple",
            "specifications": ["professional", "m3_chip", "16gb_ram", "retina_display"],
            "rating": 4.8
        }
    ]

    discovery = DiscoveryAgent(sample_products)

    # Test 1: Specific user - search first
    print("1️⃣ Specific user - search first mode:")
    specific_request = DiscoveryRequest(
        category="electronics",
        subcategory="laptop",
        specifications={"graphics": "rtx", "ram": "16gb"},
        budget="under $1500",
        user_specificity=UserSpecificity.SPECIFIC,
        discovery_mode=DiscoveryMode.SEARCH_FIRST
    )

    result1 = discovery.discover_products(specific_request)
    print(f"   Mode: {result1.discovery_mode.value}")
    print(f"   Status: {result1.status}")
    print(f"   Products found: {result1.total_found}")
    print(f"   Message: {result1.user_message[:100]}...")

    # Test 2: Vague user - recommend first
    print("\n2️⃣ Vague user - recommend first mode:")
    vague_request = DiscoveryRequest(
        category="electronics",
        subcategory="laptop",
        specifications={},
        use_case="gaming",
        user_specificity=UserSpecificity.VAGUE,
        discovery_mode=DiscoveryMode.RECOMMEND_FIRST
    )

    result2 = discovery.discover_products(vague_request)
    print(f"   Mode: {result2.discovery_mode.value}")
    print(f"   Status: {result2.status}")
    print(f"   Recommendations: {len(result2.recommendations)}")
    print(f"   Message: {result2.user_message[:100]}...")

    # Test 3: User specificity detection
    print("\n3️⃣ Testing user specificity detection:")

    specific_msg = "Show me gaming laptops with RTX 4060 and 16GB RAM under $1400"
    vague_msg = "I need a good laptop, can you recommend something?"

    spec1, mode1 = discovery.determine_user_specificity(
        {"specifications": ["rtx", "16gb"], "budget": "$1400"},
        specific_msg
    )
    print(f"   Specific message → {spec1.value}, {mode1.value}")

    spec2, mode2 = discovery.determine_user_specificity(
        {"specifications": []},
        vague_msg
    )
    print(f"   Vague message → {spec2.value}, {mode2.value}")

    print("\n" + "=" * 60)
    print("✅ Discovery Agent Tests Complete!")


if __name__ == "__main__":
    test_discovery_agent()