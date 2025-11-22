#core/planner_nlu.py

from typing import Dict, List, Optional, Any
from core.llm_client import LLMClient
from config.enums import ModelType
from prompts.DiscoveryEntityExtractionPrompt import SYSTEM_PROMPT_ENTITY_EXTRACTION
import os
import json
import re

class DiscoveryNLU:

    def __init__(self, subcategory, specification_list, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient(model_type=os.getenv("MODEL_TYPE", ModelType.openai))
        self.user_prompt: str | None = None
        self.system_prompt: str = SYSTEM_PROMPT_ENTITY_EXTRACTION
        self.subcategory = subcategory
        self.specification_list: List[Dict[str, Any]] = specification_list

    async def get_user_prompt(self, question):
        user_prompt = "Input:\n"
        user_prompt += f"Product: {self.subcategory}\n"
        user_prompt += "Available specs:\n"
        spec_list_label = [spec["spec_name_label"].lower() for spec in self.specification_list]
        for obj in self.specification_list:
            str_ = ""
            str_ += f"\t- {obj['spec_name_label']}: datatype={obj['data_type']}, "
            if obj["unit"] is not None:
                str_ += f"unit - {obj['unit']}. "
                str_ += f"example - **{obj['spec_value']} {obj['unit']}."
            else:
                str_ += f"example - {obj['spec_value']}."
            user_prompt += str_ + "\n"
        user_prompt += f"Note: Use lowercase keys exactly as listed (e.g. {', '.join(spec_list_label)}) \n"
        user_prompt += f"\nuser prompt - {question}"
        return user_prompt

    # ------------------------------------------------------------
    # CLEAN RAW RESPONSE
    # ------------------------------------------------------------
    async def extract_json_list(self, response: str) -> List[Dict[str, Any]]:
        """
        Extract a JSON array (list of dicts) from an LLM response.
        """

        if not response:
            return []

        # 1. Remove markdown code fences
        response = re.sub(r"```json", "", response, flags=re.IGNORECASE)
        response = re.sub(r"```", "", response).strip()

        # 2. Try to extract a JSON array first: [...stuff...]
        list_match = re.search(r"\[[\s\S]*\]", response)
        if list_match:
            json_str = list_match.group(0)
        else:
            # fallback: extract single object and wrap it as list
            obj_match = re.search(r"\{[\s\S]*\}", response)
            if not obj_match:
                return []
            json_str = f"[{obj_match.group(0)}]"

        # 3. Fix trailing commas (LLM common issue)
        json_str = re.sub(r",\s*(\}|\])", r"\1", json_str)

        # 4. Load JSON safely
        try:
            return json.loads(json_str)
        except Exception:
            # last fallback: repair missing quotes around keys
            repaired = re.sub(r"(\w+)\s*:", r'"\1":', json_str)
            repaired = re.sub(r",\s*(\}|\])", r"\1", repaired)
            try:
                return json.loads(repaired)
            except Exception:
                return []

    async def run(self, user_query: str) -> List[Dict] | None:
        self.user_prompt = await self.get_user_prompt(user_query)
        try:
            raw_llm_output = await self.llm_client.generate(self.system_prompt, self.user_prompt)
        except Exception as e:
            print(f"Discovery NLU caught exception: {e}")
            return None
        llm_output_list = await self.extract_json_list(raw_llm_output)
        return llm_output_list

import asyncio

if __name__ == "__main__":

    specification_list = [
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

    async def main():
        dnlu = DiscoveryNLU(subcategory="laptop", specification_list=specification_list)
        user_query = "I need something under 2000 USD and Graphics should be Apple GPU"
        output = await dnlu.run(user_query)
        print(output)

    asyncio.run(main())
    chk = 1

