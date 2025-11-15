import asyncio
import json
from pathlib import Path
from typing import Dict, List

from agents.QueryAgent import QueryAgent
from core.QueryExecutor import QueryExecutorSimple

DB_DIR = Path(__file__).resolve().parent.parent / "db"
REQUIRED_FILES = ["product.json", "specification.json"]

for filename in REQUIRED_FILES:
    path = DB_DIR / filename
    if not path.exists():
        raise FileNotFoundError(f"Required data file missing: {path}")

SCENARIOS: List[Dict] = [
    {
        "name": "Laptops second cheapest (RAM >=8GB)",
        "current_query": "Show me the second cheapest laptop with at least 8GB RAM",
        "category": "laptop",
        "turns": [
            {
                "user_query": "I need a laptop",
                "entities": [
                    {"key": "subcategory_name", "value": "laptop", "operator": "="},
                ],
                "agent_response": "Any particular requirements?",
            },
            {
                "user_query": "Make sure it has at least 8 GB of RAM",
                "entities": [
                    {"key": "ram", "value": 8, "operator": ">=", "unit": "GB"},
                ],
                "agent_response": "Got it.",
            },
        ],
        "llm_output": {
            "pandas_query": """import pandas as pd\nimport numpy as np\n\n# Filter laptops\ndf_filtered_products = df_product[\n    df_product['subcategory_name'].str.lower() == 'laptop'\n].copy()\n\n# Extract RAM specs and enforce numeric comparison\ndf_ram_specs = df_specification[\n    df_specification['spec_name'].str.lower() == 'ram'\n].copy()\ndf_ram_specs['spec_value_numeric'] = pd.to_numeric(\n    df_ram_specs['spec_value'].str.extract(r'(\\d+(?:\\.\\d+)?)')[0],\n    errors='coerce'\n)\n\n# Keep products with RAM >= 8\ndf_ram_filtered = df_ram_specs[df_ram_specs['spec_value_numeric'] >= 8][['product_id']]\n\n# Merge with product catalog\ndf_with_ram = df_filtered_products.merge(\n    df_ram_filtered,\n    on='product_id',\n    how='inner'\n)\n\n# Sort by price ascending\ndf_sorted = df_with_ram.sort_values('price').reset_index(drop=True)\n\nif len(df_sorted) >= 2:\n    df_result = pd.DataFrame([df_sorted.iloc[1]])\nelse:\n    df_result = df_sorted.copy()\n\ndf_result""",
            "reasoning": "Filtered laptops to those with RAM >= 8GB and selected the second cheapest entry.",
        },
    },
    {
        "name": "Laptops third option (battery >=11h)",
        "current_query": "Show me the third cheapest laptop with battery life of at least 11 hours",
        "category": "laptop",
        "turns": [
            {
                "user_query": "I'm looking for laptops under $2500",
                "entities": [
                    {"key": "subcategory_name", "value": "laptop", "operator": "="},
                    {"key": "price", "value": 2500, "operator": "<="},
                ],
                "agent_response": "Any other preferences?",
            },
            {
                "user_query": "Battery life should be at least 11 hours",
                "entities": [
                    {"key": "battery_life", "value": 11, "operator": ">=", "unit": "hours"},
                ],
                "agent_response": "Sure, let me narrow that down.",
            },
        ],
        "llm_output": {
            "pandas_query": """import pandas as pd\nimport numpy as np\n\n# Filter laptops within budget\ndf_filtered_products = df_product[\n    (df_product['subcategory_name'].str.lower() == 'laptop') &\n    (df_product['price'] <= 2500)\n].copy()\n\n# Extract battery life specs\ndf_battery_specs = df_specification[\n    df_specification['spec_name'].str.lower() == 'battery_life'\n].copy()\ndf_battery_specs['spec_value_numeric'] = pd.to_numeric(\n    df_battery_specs['spec_value'].str.extract(r'(\\d+(?:\\.\\d+)?)')[0],\n    errors='coerce'\n)\n\n# Keep products with battery life >= 11 hours\ndf_battery_filtered = df_battery_specs[df_battery_specs['spec_value_numeric'] >= 11][['product_id']]\n\n# Merge with product catalog\ndf_with_battery = df_filtered_products.merge(\n    df_battery_filtered,\n    on='product_id',\n    how='inner'\n)\n\n# Sort by price and pick the third option if available\ndf_sorted = df_with_battery.sort_values('price').reset_index(drop=True)\n\nif len(df_sorted) >= 3:\n    df_result = pd.DataFrame([df_sorted.iloc[2]])\nelse:\n    df_result = df_sorted.copy()\n\ndf_result""",
            "reasoning": "Filtered laptops under $2500 with battery life >= 11 hours, then selected the third cheapest.",
        },
    },
    {
        "name": "Dumbbells adjustable between 3 and 30 kg",
        "current_query": "Find adjustable dumbbells between 3kg and 30kg",
        "category": "dumbbells",
        "turns": [
            {
                "user_query": "Show me adjustable dumbbells",
                "entities": [
                    {"key": "subcategory_name", "value": "dumbbells", "operator": "="},
                    {"key": "adjustable", "value": "Yes", "operator": "="}
                ],
                "agent_response": "Any weight preference?",
            },
            {
                "user_query": "Between 3 and 30 kilograms",
                "entities": [
                    {"key": "min_weight", "value": 3, "operator": ">=", "unit": "kilograms"},
                    {"key": "max_weight", "value": 30, "operator": "<=", "unit": "kilograms"}
                ],
                "agent_response": "Filtering adjustable dumbbells in that range.",
            },
        ],
        "llm_output": {
            "pandas_query": """import pandas as pd\nimport numpy as np\n\n# Filter dumbbells\ndf_filtered_products = df_product[\n    df_product['subcategory_name'].str.lower() == 'dumbbells'\n].copy()\n\n# Grab relevant specifications\ndf_specs = df_specification[\n    df_specification['spec_name'].str.lower().isin(['min_weight', 'max_weight', 'adjustable'])\n].copy()\n\ndf_specs['spec_name_lower'] = df_specs['spec_name'].str.lower()\ndf_specs_pivot = df_specs.pivot_table(\n    index='product_id',\n    columns='spec_name_lower',\n    values='spec_value',\n    aggfunc='first'\n).reset_index()\n\n# Convert weight values to numeric\ndf_specs_pivot['min_weight_numeric'] = pd.to_numeric(\n    df_specs_pivot['min_weight'].str.extract(r'(\\d+(?:\\.\\d+)?)')[0],\n    errors='coerce'\n)\ndf_specs_pivot['max_weight_numeric'] = pd.to_numeric(\n    df_specs_pivot['max_weight'].str.extract(r'(\\d+(?:\\.\\d+)?)')[0],\n    errors='coerce'\n)\n\n# Apply filters\ndf_specs_filtered = df_specs_pivot[\n    (df_specs_pivot['min_weight_numeric'] >= 3) &\n    (df_specs_pivot['max_weight_numeric'] <= 30) &\n    (df_specs_pivot['adjustable'].str.lower() == 'yes')\n]\n\n# Merge with product catalog\ndf_result = df_filtered_products.merge(\n    df_specs_filtered[['product_id']],\n    on='product_id',\n    how='inner'\n).sort_values('price').reset_index(drop=True)\n\nif df_result.empty:\n    df_result = df_filtered_products.iloc[0:0].copy()\n\ndf_result""",
            "reasoning": "Pivoted dumbbell specs, converted weights to numeric, filtered adjustable sets in 3-30kg range, merged back to catalog.",
        },
    },
    {
        "name": "Dumbbells with rubber material",
        "current_query": "List dumbbells made of rubber sorted by price",
        "category": "dumbbells",
        "turns": [
            {
                "user_query": "Show me dumbbells",
                "entities": [
                    {"key": "subcategory_name", "value": "dumbbells", "operator": "="}
                ],
                "agent_response": "Any specific material?",
            },
            {
                "user_query": "Prefer rubber coating",
                "entities": [
                    {"key": "material", "value": "Rubber", "operator": "contains"}
                ],
                "agent_response": "Filtering dumbbells with rubber material.",
            }
        ],
        "llm_output": {
            "pandas_query": """import pandas as pd\nimport numpy as np\n\n# Filter dumbbells\ndf_filtered_products = df_product[\n    df_product['subcategory_name'].str.lower() == 'dumbbells'\n].copy()\n\n# Material specifications\ndf_material = df_specification[\n    df_specification['spec_name'].str.lower() == 'material'\n].copy()\n\ndf_material = df_material[\n    df_material['spec_value'].str.contains('rubber', case=False, na=False)\n][['product_id']]\n\n# Merge and sort by price\ndf_result = df_filtered_products.merge(\n    df_material,\n    on='product_id',\n    how='inner'\n).sort_values('price').reset_index(drop=True)\n\nif df_result.empty:\n    df_result = df_filtered_products.iloc[0:0].copy()\n\ndf_result""",
            "reasoning": "Filtered dumbbells via material specs containing 'rubber' and sorted by price.",
        },
    },
]


async def run_scenario(scenario: Dict) -> None:
    print(f"\n=== Scenario: {scenario['name']} ===")

    agent = QueryAgent()

    result = await agent.run(
        current_query=scenario["current_query"],
        turns=scenario["turns"],
        category=scenario.get("category"),
    )

    pandas_query = result.get("pandas_query")
    if not pandas_query:
        print("No pandas_query produced.")
        return

    executor = QueryExecutorSimple(pandas_query, data_dir=str(DB_DIR))
    df_result = executor.execute()

    if df_result is not None:
        print("Result shape:", df_result.shape)
        print(df_result)


async def main() -> None:
    for scenario in SCENARIOS:
        await run_scenario(scenario)


if __name__ == "__main__":
    asyncio.run(main())
