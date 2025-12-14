import asyncio
import sys
import types

def _ensure_dotenv_stub():
    """
    Provide a no-op dotenv stub if python-dotenv is not installed.
    This keeps local demos working without extra installs.
    """
    if "dotenv" in sys.modules:
        return
    try:
        import dotenv  # noqa: F401
    except Exception:
        dotenv = types.ModuleType("dotenv")
        dotenv.load_dotenv = lambda: None
        sys.modules["dotenv"] = dotenv


async def main():
    _ensure_dotenv_stub()
    from agents.SummarizerAgent import SummarizerAgent

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
                    {"product_id": 1, "product_name": "Apple MacBook Air M2", "brand": "Apple", "price": 1694, "stock_quantity": 465},
                    {"product_id": 2, "product_name": "Apple MacBook Pro M3", "brand": "Apple", "price": 1619, "stock_quantity": 390},
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
                {"user_message": "Show laptops under $2000.", "ai_message": "Included Dell XPS 13 with battery 12h, price $1700."}
            ],
            "query_result": {
                "row_count": 3,
                "columns": ["product_id", "product_name", "brand", "price", "battery_life"],
                "preview": [
                    {"product_id": 3, "product_name": "Dell XPS 13", "brand": "Dell", "price": 1700, "battery_life": "12h"},
                    {"product_id": 5, "product_name": "Lenovo ThinkPad X1", "brand": "Lenovo", "price": 1182, "battery_life": "11h"},
                    {"product_id": 10, "product_name": "Samsung Galaxy Book3", "brand": "Samsung", "price": 969, "battery_life": "9h"},
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
    asyncio.run(main())
