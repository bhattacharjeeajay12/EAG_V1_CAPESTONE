
# tools/registry.py (expanded)
from typing import Callable, Dict, Awaitable, Any, List
import asyncio
from tools.tools import (
    CatalogSemanticSearch, RecommenderRank,
    PaymentsCharge, ReturnsCheckEligibility, ExchangesCheckEligibility
)

class ToolRegistry:
    """
    Async registry facade. All tool handlers are awaited, even if implemented via local sync stubs.
    """
    def __init__(self):
        # Local stubs / adapters
        self._search = CatalogSemanticSearch()
        self._rank = RecommenderRank()
        self._payments = PaymentsCharge()
        self._returns = ReturnsCheckEligibility()
        self._exchanges = ExchangesCheckEligibility()

        # Registry map
        self._registry: Dict[str, Callable[[Dict[str, Any]], Awaitable[Any]]] = {
            # Discovery family
            "filter_products": self._filter_products,
            "get_product_reviews": self._get_product_reviews,
            "rank_products_by_reviews": self._rank_products_by_reviews,
            "rank_products_by_review_count": self._rank_products_by_review_count,
            "filter_products_by_review_votes": self._filter_products_by_review_votes,
            "compare_reviews": self._compare_reviews,

            # Order
            "place_order": self._place_order,

            # Payments / Returns / Exchanges
            "Payments.charge": self._payments_charge,
            "Returns.check_eligibility": self._returns_check_eligibility,
            "Exchanges.check_eligibility": self._exchanges_check_eligibility,
        }

    async def call(self, name: str, params: dict):
        tool = self._registry.get(name)
        if not tool:
            raise ValueError(f"Unknown tool: {name}")
        return await tool(params)

    # ----------------- Discovery tools -----------------
    async def _filter_products(self, params: dict) -> List[Dict[str, Any]]:
        items = self._search({
            "subcategory": params.get("subcategory"),
            "product_hint": params.get("brand") or ""
        }, top_k=12)
        pr = params.get("price_range")
        if pr and isinstance(pr, (list, tuple)) and len(pr) == 2:
            lo, hi = pr
            items = [p for p in items if lo <= p.get("price", 0) <= hi]
        result = self._rank(items)
        await asyncio.sleep(0)
        return result

    async def _get_product_reviews(self, params: dict):
        await asyncio.sleep(0)
        pid = params.get("product_id") or 0
        # Emulated rows
        return [
            {"review_id": f"r_{pid}_1", "rating": 5, "title": "Great", "text": "Loved it", "helpful_votes_count": 10},
            {"review_id": f"r_{pid}_2", "rating": 4, "title": "Good", "text": "Solid choice", "helpful_votes_count": 3},
        ]

    async def _rank_products_by_reviews(self, params: dict):
        await asyncio.sleep(0)
        sub = params.get("subcategory") or "laptop"
        # Emulated ranking
        return [
            {"product_id": f"{sub}_a", "product_name": f"{sub.title()} A", "avg_rating": 4.7, "review_count": 120},
            {"product_id": f"{sub}_b", "product_name": f"{sub.title()} B", "avg_rating": 4.5, "review_count": 85},
        ]

    async def _rank_products_by_review_count(self, params: dict):
        await asyncio.sleep(0)
        sub = params.get("subcategory") or "laptop"
        return [
            {"product_id": f"{sub}_x", "product_name": f"{sub.title()} X", "review_count": 500, "avg_rating": 4.2},
            {"product_id": f"{sub}_y", "product_name": f"{sub.title()} Y", "review_count": 420, "avg_rating": 4.1},
        ]

    async def _filter_products_by_review_votes(self, params: dict):
        await asyncio.sleep(0)
        pid = params.get("product_id") or "demo"
        min_votes = params.get("min_helpful_votes") or 5
        return [
            {"review_id": f"{pid}_rv1", "helpful_votes_count": 12, "rating": 5, "text": "Super helpful"},
            {"review_id": f"{pid}_rv2", "helpful_votes_count": 6, "rating": 4, "text": "Pretty good"},
        ][: max(1, min_votes // 5)]

    async def _compare_reviews(self, params: dict):
        await asyncio.sleep(0)
        ids = params.get("compare_ids") or []
        return [
            {"entity": str(e), "avg_rating": 4.3, "review_count": 200, "top_positive_highlights": ["battery"], "top_negative_highlights": ["weight"]}
            for e in ids
        ]

    # ----------------- Order & others -----------------
    async def _place_order(self, params: dict):
        await asyncio.sleep(0)
        return {"order_id": "ord_123", "product_id": params.get("product_id"), "status": "confirmed"}

    async def _payments_charge(self, params: dict):
        await asyncio.sleep(0)
        return self._payments(method=params.get("method"), amount=params.get("amount"))

    async def _returns_check_eligibility(self, params: dict):
        await asyncio.sleep(0)
        return self._returns(order_id=params.get("order_id"))

    async def _exchanges_check_eligibility(self, params: dict):
        await asyncio.sleep(0)
        return self._exchanges(order_id=params.get("order_id"))
