import asyncio
import json
from pathlib import Path
from typing import Dict, List

import pandas as pd

from agents.QueryAgent import QueryAgent
from core.QueryExecutor import QueryExecutorSimple

TEMP_DB_DIR = Path(__file__).resolve().parent / "tmp_db"
TEMP_DB_DIR.mkdir(parents=True, exist_ok=True)

PRODUCT_ROWS: List[Dict] = [
    {"product_id": "p1", "brand": "Dell", "subcategory_name": "laptop", "price_usd": 900, "stock_quantity": 5},
    {"product_id": "p2", "brand": "Dell", "subcategory_name": "laptop", "price_usd": 950, "stock_quantity": 7},
    {"product_id": "p3", "brand": "Dell", "subcategory_name": "laptop", "price_usd": 1100, "stock_quantity": 4},
    {"product_id": "p4", "brand": "Apple", "subcategory_name": "smartphone", "price_usd": 850, "stock_quantity": 10},
    {"product_id": "p5", "brand": "Apple", "subcategory_name": "smartphone", "price_usd": 920, "stock_quantity": 8},
    {"product_id": "p6", "brand": "Apple", "subcategory_name": "smartphone", "price_usd": 1000, "stock_quantity": 6},
    {"product_id": "p7", "brand": "Apple", "subcategory_name": "smartphone", "price_usd": 1150, "stock_quantity": 9},
]

SPEC_ROWS: List[Dict] = [
    {"product_id": "p1", "spec_name": "ram", "spec_value": "8 GB", "unit": "GB"},
    {"product_id": "p2", "spec_name": "ram", "spec_value": "16 GB", "unit": "GB"},
    {"product_id": "p3", "spec_name": "ram", "spec_value": "32 GB", "unit": "GB"},
    {"product_id": "p4", "spec_name": "battery_life", "spec_value": "18 hours", "unit": "hours"},
    {"product_id": "p5", "spec_name": "battery_life", "spec_value": "22 hours", "unit": "hours"},
    {"product_id": "p6", "spec_name": "battery_life", "spec_value": "24 hours", "unit": "hours"},
    {"product_id": "p7", "spec_name": "battery_life", "spec_value": "28 hours", "unit": "hours"},
]

pd.DataFrame(PRODUCT_ROWS).to_json(TEMP_DB_DIR / "product.json", orient="records", indent=2)
pd.DataFrame(SPEC_ROWS).to_json(TEMP_DB_DIR / "specification.json", orient="records", indent=2)

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
                    {"key": "ram", "value": 16, "operator": ">=", "unit": "GB"},
                ],
                "agent_response": "Any preference for storage?",
            },
        ],
        "llm_output": {
            "pandas_query": """import pandas as pd\nimport numpy as np\n\n# Filter products by brand and subcategory\ndf_filtered_products = df_product[\n    (df_product['brand'].str.lower() == 'dell') & \n    (df_product['subcategory_name'].str.lower() == 'laptop')\n].copy()\n\n# Filter specifications for RAM using regex for robust extraction\ndf_ram_specs = df_specification[\n    df_specification['spec_name'].str.lower() == 'ram'\n].copy()\ndf_ram_specs['spec_value_numeric'] = pd.to_numeric(\n    df_ram_specs['spec_value'].str.extract(r'(\\d+(?:\\.\\d+)?)')[0], \n    errors='coerce'\n)\n\n# Filter RAM >= 16\ndf_ram_filtered = df_ram_specs[df_ram_specs['spec_value_numeric'] >= 16][['product_id']]\n\n# Merge to get products with RAM >= 16GB\ndf_with_ram = df_filtered_products.merge(\n    df_ram_filtered, \n    on='product_id', \n    how='inner'\n)\n\n# Sort by price to establish order\ndf_sorted = df_with_ram.sort_values('price_usd').reset_index(drop=True)\n\n# Get the second product with error handling\nif len(df_sorted) >= 2:\n    df_result = pd.DataFrame([df_sorted.iloc[1]])\nelse:\n    # Return empty DataFrame with proper structure if insufficient products\n    df_result = pd.DataFrame(columns=df_sorted.columns)\n\ndf_result""",
            "reasoning": "Stubbed reasoning",
        },
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
                    {"key": "battery_life", "value": 20, "operator": ">", "unit": "hours"},
                ],
                "agent_response": "Here you go.",
            },
        ],
        "llm_output": {
            "pandas_query": """import pandas as pd\nimport numpy as np\n\n# Filter products by brand and subcategory\ndf_filtered_products = df_product[\n    (df_product['brand'].str.lower() == 'apple') & \n    (df_product['subcategory_name'].str.lower() == 'smartphone') & \n    (df_product['price_usd'] >= 800) & \n    (df_product['price_usd'] <= 1200)\n].copy()\n\n# Filter specifications for battery life using regex\ndf_battery_specs = df_specification[\n    df_specification['spec_name'].str.lower() == 'battery_life'\n].copy()\ndf_battery_specs['spec_value_numeric'] = pd.to_numeric(\n    df_battery_specs['spec_value'].str.extract(r'(\\d+(?:\\.\\d+)?)')[0], \n    errors='coerce'\n)\n\n# Filter for battery life > 20 hours\ndf_battery_filtered = df_battery_specs[df_battery_specs['spec_value_numeric'] > 20][['product_id']]\n\n# Merge to get products with battery life > 20 hours\ndf_result = df_filtered_products.merge(\n    df_battery_filtered, \n    on='product_id', \n    how='inner'\n)\n\n# Sort by price to establish order\ndf_result = df_result.sort_values('price_usd').reset_index(drop=True)\n\n# Get the third product with error handling\nif len(df_result) >= 3:\n    df_result = pd.DataFrame([df_result.iloc[2]])\nelse:\n    df_result = pd.DataFrame(columns=df_result.columns)\n\ndf_result""",
            "reasoning": "Stubbed reasoning",
        },
    },
]


async def run_scenario(scenario: Dict) -> None:
    print(f"\n=== Scenario: {scenario['name']} ===")

    agent = QueryAgent()

    # async def fake_generate(system_prompt: str, user_prompt: str) -> str:
    #     return json.dumps(scenario["llm_output"])

    # agent.llm_client.generate = fake_generate  # type: ignore

    result = await agent.run(
        current_query=scenario["current_query"],
        turns=scenario["turns"],
        category=scenario.get("category"),
    )

    pandas_query = result.get("pandas_query")
    if not pandas_query:
        print("No pandas_query produced.")
        return

    executor = QueryExecutorSimple(pandas_query, data_dir=str(TEMP_DB_DIR))
    df_result = executor.execute()

    if df_result is not None:
        print("Result shape:", df_result.shape)
        print(df_result)


async def main() -> None:
    for scenario in SCENARIOS:
        await run_scenario(scenario)


if __name__ == "__main__":
    asyncio.run(main())
