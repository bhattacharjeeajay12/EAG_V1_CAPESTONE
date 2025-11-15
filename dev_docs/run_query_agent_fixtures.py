import asyncio
import json
from pathlib import Path
from typing import Dict, List

import numpy as np
import pandas as pd

from agents.QueryAgent import QueryAgent

FIXTURE_DIR = Path(__file__).resolve().parent / "db"

TABLE_FILES = {
    "df_user": "user.json",
    "df_buy_history": "buy_history.json",
    "df_category": "category.json",
    "df_subcategory": "subcategory.json",
    "df_product": "product.json",
    "df_specification": "specification.json",
    "df_return_history": "return_history.json",
    "df_review": "review.json",
}


def load_dataframes() -> Dict[str, pd.DataFrame]:
    dataframes: Dict[str, pd.DataFrame] = {}
    for df_name, filename in TABLE_FILES.items():
        path = FIXTURE_DIR / filename
        if not path.exists():
            raise FileNotFoundError(f"Expected fixture not found: {path}")
        dataframes[df_name] = pd.read_json(path)
    return dataframes


SCENARIOS: List[Dict] = [
    {
        "name": "Dell laptops second cheapest",
        "current_query": "Show me the second cheapest Dell laptop with at least 16GB RAM",
        "category": "laptop",
        "turns": [
            {
                "user_query": "I need a Dell laptop",
                "entities": [
                    {"key": "subcategory_name", "value": "laptop", "operator": "="},
                    {"key": "brand", "value": "Dell", "operator": "="},
                ],
                "agent_response": "What specifications are important to you?",
            },
            {
                "user_query": "16GB RAM would be great",
                "entities": [
                    {"key": "ram", "value": 16, "operator": ">=", "unit": "GB"}
                ],
                "agent_response": "Any preference for storage?",
            },
        ],
    },
    {
        "name": "Apple smartphones third option",
        "current_query": "Show me the third option with full specs",
        "category": "smartphone",
        "turns": [
            {
                "user_query": "I need Apple phones between $800 and $1200",
                "entities": [
                    {"key": "subcategory_name", "value": "smartphone", "operator": "="},
                    {"key": "brand", "value": "Apple", "operator": "="},
                    {"key": "price_usd", "value": [800, 1200], "operator": "between"},
                ],
                "agent_response": "Found 4 matches.",
            },
            {
                "user_query": "Add requirement: battery life over 20 hours",
                "entities": [
                    {"key": "battery_life", "value": 20, "operator": ">", "unit": "hours"}
                ],
                "agent_response": "Here you go.",
            },
        ],
    },
]


def sanitize_generated_code(code: str) -> str:
    """Normalize LLM-generated pandas code for execution."""
    if not isinstance(code, str):
        return ""
    normalized = code.replace("\r\n", "\n").replace("\r", "\n").strip()
    try:
        normalized = bytes(normalized, "utf-8").decode("unicode_escape")
    except Exception:
        pass
    normalized = normalized.replace("\\\n", "\n")
    return normalized.strip()


async def run_scenario(agent: QueryAgent, data_env: Dict[str, pd.DataFrame], scenario: Dict) -> None:
    print(f"\n=== Scenario: {scenario['name']} ===")
    result = await agent.run(
        current_query=scenario["current_query"],
        turns=scenario["turns"],
        category=scenario.get("category"),
    )

    pandas_query = result.get("pandas_query")
    if not pandas_query:
        print("No pandas_query returned:\n", json.dumps(result, indent=2))
        return

    sanitized_query = sanitize_generated_code(pandas_query)

    print("-- Reasoning --")
    print(result.get("reasoning", "<none>"))
    print("-- Sanitized pandas query --")
    print(sanitized_query)
    print("-- Executing generated pandas query --")

    # Prepare execution environment with dataframes and libraries
    exec_env: Dict[str, object] = {"pd": pd, "np": np}
    exec_env.update(data_env)

    try:
        exec(sanitized_query, exec_env)
    except Exception as exc:
        print("Execution failed:", exc)
        print("Problematic code snippet (repr):")
        print(repr(sanitized_query[:2000]))
        return

    df_result = exec_env.get("df_result")
    if df_result is None:
        print("No df_result produced by generated code.")
    else:
        print("Result shape:", df_result.shape)
        print(df_result.head())


async def main() -> None:
    data_env = load_dataframes()
    agent = QueryAgent()

    for scenario in SCENARIOS:
        await run_scenario(agent, data_env, scenario)


if __name__ == "__main__":
    asyncio.run(main())
