from typing import Dict, Any, List, Optional
from config.enums import Agents
from prompts.DiscoveryEntityExtractionPrompt import SYSTEM_PROMPT_ENTITY_EXTRACTION
from nlu.discovery_nlu import DiscoveryNLU

import os
import asyncio
from config.enums import ModelType
from core.llm_client import LLMClient


class DiscoveryAgent:
    def __init__(self, subcategory: str) -> None:
        self.subcategory = subcategory
        self.llm = LLMClient(model_type=os.getenv("MODEL_TYPE", ModelType.openai))
        spec_nlu = None
        spec_nlu_response = None

        self.spec_asked: List[Dict[str, Any]] = []

    async def ask_specification(self, user_given_specs, specification_list):
        user_given_specs_keys = [obj["key"] for obj in user_given_specs]
        given_specs, other_available_specs = [], []
        for obj in specification_list:
            if obj["key"] in user_given_specs_keys:
                given_specs.append(obj)
            else:
                other_available_specs.append(obj)
        return {"given_specs": given_specs, "other_available_specs": other_available_specs}

    async def create_spec_statement(self, user_given_specs, specification_list):
        dict_ = self.ask_specification(user_given_specs, specification_list)

        table_rows = ["spec_name_label, example"]
        for spec in dict_["other_available_specs"]:
            label = spec["spec_name_label"]
            value = spec["spec_value"]
            unit = spec["unit"]
            example = f"{value} {unit}" if unit else value
            table_rows.append(f"{label}, {example}")

        final_table = "\n".join(table_rows)
        return final_table



    async def run(self, user_query: str, specification_list, specification_ask=False) -> Dict[str, Any]:
        self.spec_nlu = DiscoveryNLU(self.subcategory, specification_list)
        self.spec_nlu_response = await self.spec_nlu.run(user_query)
        if self.spec_nlu_response is None:
            raise ValueError("Discovery NLU response is None. Please investigate.")
        if specification_ask:
            await self.create_spec_statement(self.spec_nlu_response, specification_list)

        return {}


# ---------------------------
# FIX: proper async execution
# ---------------------------
if __name__ == "__main__":
    specification_list_ = [
        {'data_type': 'text', 'spec_name': 'Brand', 'spec_name_label': 'Brand', 'spec_value': 'Apple', 'unit': None},
        {'data_type': 'text', 'spec_name': 'Processor', 'spec_name_label': 'Processor', 'spec_value': 'Apple M3', 'unit': None},
        {'data_type': 'integer', 'spec_name': 'RAM', 'spec_name_label': 'RAM', 'spec_value': '8', 'unit': 'gigabytes'},
        {'data_type': 'integer', 'spec_name': 'Storage', 'spec_name_label': 'Storage', 'spec_value': '256', 'unit': 'gigabytes'},
        {'data_type': 'float', 'spec_name': 'Display_Size', 'spec_name_label': 'Display Size', 'spec_value': '13.6', 'unit': 'inches'},
        {'data_type': 'integer', 'spec_name': 'Battery_Life', 'spec_name_label': 'Battery Life', 'spec_value': '18', 'unit': 'hours'},
        {'data_type': 'float', 'spec_name': 'Weight', 'spec_name_label': 'Weight', 'spec_value': '1.49', 'unit': 'kilograms'},
        {'data_type': 'text', 'spec_name': 'Operating_System', 'spec_name_label': 'Operating System', 'spec_value': 'macOS', 'unit': None},
        {'data_type': 'text', 'spec_name': 'Graphics', 'spec_name_label': 'Graphics', 'spec_value': 'Apple GPU', 'unit': None},
        {'data_type': 'integer', 'spec_name': 'Warranty', 'spec_name_label': 'Warranty', 'spec_value': '1', 'unit': 'years'},
        {'data_type': 'float', 'spec_name': 'Price', 'spec_name_label': 'Price', 'spec_value': '1694', 'unit': 'USD'}
    ]

    # {'key': 'price', 'operator': 'BETWEEN', 'unit': 'USD', 'value': [0, 5000]}

    async def main():
        discovery_agent = DiscoveryAgent(
            subcategory="laptop",
            specification_list=specification_list_,
            specification_ask= True
        )
        result = await discovery_agent.run(user_query="I need a laptop with price under 5000 USD.", specification_ask = True)
        print(result)

    # RUN async function properly
    asyncio.run(main())
