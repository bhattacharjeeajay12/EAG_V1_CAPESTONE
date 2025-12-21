import json
from typing import Any, Dict, List, Optional

from config.enums import ChatInfo
from core.llm_client import LLMClient
from prompts.Summarizer import get_summarizer_prompt


class SummarizerAgent:
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()

    async def _build_user_prompt(
        self,
        current_query: str,
        chats: List[Dict[str, Any]],
        query_result: Optional[Dict[str, Any]],
        history_limit: int = 5,
    ) -> str:
        trimmed_chats = []
        for chat in chats[-history_limit:]:
            trimmed_chats.append(
                {
                    ChatInfo.user_message.value: chat.get(ChatInfo.user_message.value),
                    ChatInfo.ai_message.value: chat.get(ChatInfo.ai_message.value),
                }
            )

        qr_payload = None
        if query_result:
            qr_payload = {
                "row_count": query_result.get("row_count", 0),
                "columns": query_result.get("columns", []),
                "preview": query_result.get("preview", []),
            }

        payload = {
            "current_query": current_query,
            "conversation_history": trimmed_chats,
            "query_result": qr_payload,
        }
        return json.dumps(payload, indent=2)

    async def _parse_llm_json(self, text: str) -> Dict[str, Any]:
        cleaned = text.replace("```json", "").replace("```", "").strip()
        try:
            start = cleaned.find("{")
            end = cleaned.rfind("}")
            if start != -1 and end != -1:
                cleaned = cleaned[start : end + 1]
            return json.loads(cleaned)
        except Exception:
            return {"answer": cleaned}

    def _format_response(self, parsed: Dict[str, Any]) -> str:
        answer = parsed.get("answer")

        if not answer:
            return ""
        return str(answer).strip()

    async def run(
        self,
        current_query: str,
        chats: List[Dict[str, Any]],
        query_result: Optional[Dict[str, Any]] = None,
    ) -> str:
        system_prompt = get_summarizer_prompt()
        user_prompt = await self._build_user_prompt(current_query, chats, query_result)
        raw_response = await self.llm_client.generate(system_prompt, user_prompt)
        parsed = await self._parse_llm_json(raw_response)
        return self._format_response(parsed)

async def main():
    agent = SummarizerAgent()

    scenarios = [
        {
            "name": "Two laptops",
            "current_query": "Show me the second cheapest Apple laptop with >=8GB RAM",
            "chats": [
                {"user_message": "Show me Apple laptops with at least 8GB RAM.", "ai_message": "Sure, I'll check."},
            ],
            "query_result": {
                "row_count": 2,
                "columns": ["product_id", "product_name", "brand", "price", "stock_quantity"],
                "preview": [
                    {"product_id": 1, "product_name": "Apple MacBook Air M2", "brand": "Apple", "price": 1694,
                     "stock_quantity": 465},
                    {"product_id": 2, "product_name": "Apple MacBook Pro M3", "brand": "Apple", "price": 1619,
                     "stock_quantity": 390},
                ],
            },
        },
        {
            "name": "No matches",
            "current_query": "Show dumbbells made of titanium",
            "chats": [],
            "query_result": {
                "row_count": 0,
                "columns": ["product_id", "product_name", "brand", "price"],
                "preview": [],
            },
        },
        {
            "name": "History already has the answer",
            "current_query": "What was the battery life of that Dell you showed?",
            "chats": [
                {"user_message": "Show laptops under $2000.",
                 "ai_message": "Included Dell XPS 13 with battery 12h, price $1700."}
            ],
            "query_result": {
                "row_count": 3,
                "columns": ["product_id", "product_name", "brand", "price", "battery_life"],
                "preview": [
                    {"product_id": 3, "product_name": "Dell XPS 13", "brand": "Dell", "price": 1700,
                     "battery_life": "12h"},
                    {"product_id": 5, "product_name": "Lenovo ThinkPad X1", "brand": "Lenovo", "price": 1182,
                     "battery_life": "11h"},
                    {"product_id": 10, "product_name": "Samsung Galaxy Book3", "brand": "Samsung", "price": 969,
                     "battery_life": "9h"},
                ],
            },
        },
    ]

    for scenario in scenarios:
        print(f"\n=== Scenario: {scenario['name']} ===")
        out = await agent.run(
            current_query=scenario["current_query"],
            chats=scenario["chats"],
            query_result=scenario["query_result"],
        )
        print(out)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())