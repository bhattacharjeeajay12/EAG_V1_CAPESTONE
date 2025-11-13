from core.llm_client import LLMClient
from prompts.EntityExtraction import get_system_entity_prompt_discovery
from config.constants import SPECIFICATIONS
from typing import Any, Dict, List, Optional
import json
import ast
import logging
from config.utils import get_specification_list

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


class EntityExtractionAgent:
    def __init__(self, user_prompt):
        self.llm_client = LLMClient()
        self.system_prompt: Optional[str] = None
        self.user_prompt = user_prompt
        self.entities: List[Dict[str, Any]] = []
        self.available_specs: List[str] = []
        self.specifications_string: Optional[str] = None
        self.llm_output = []
        self.subcategory = None

    async def parse_llm_output(self, llm_output: str):
        """
        Parse the LLM output string (which represents JSON) into a Python list of dictionaries.

        Handles minor formatting issues such as:
        - single quotes instead of double quotes
        - extra whitespace
        - trailing commas
        """
        if not llm_output:
            return []

        try:
            # First try direct JSON parsing (most reliable)
            return json.loads(llm_output)
        except json.JSONDecodeError:
            # If JSON fails, fall back to ast.literal_eval (safe for Python-style lists)
            try:
                return ast.literal_eval(llm_output)
            except Exception as e:
                print(f"⚠️ Could not parse LLM output: {e}")
                return []

    async def get_user_prompt(self, question):
        user_prompt = "Input:\n"
        user_prompt += f"Product: {self.subcategory}\n"
        user_prompt += "Available specs:\n"
        spec_list_label = [spec["spec_name_label"].lower() for spec in self.spec_list]
        for obj in self.spec_list:
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

    async def extract_entities(self, llm_output_dict):
        entities = []
        return entities

    async def get_system_prompt(self, phase, product_name="laptop"):
        try:
            if phase == "discovery":
                return get_system_entity_prompt_discovery(product_name, self.specifications_string)
        except Exception as e:
            raise ValueError(f"Error generating system prompt: {e}")

    async def run(self, question, product_name="laptop", phase="discovery"):
        self.spec_list = get_specification_list(product_name)
        self.subcategory = product_name
        self.user_prompt = await self.get_user_prompt(question)
        self.system_prompt = await self.get_system_prompt(phase, product_name)
        raw_llm_output = await self.llm_client.generate(self.system_prompt, self.user_prompt)
        llm_output_dict = await self.parse_llm_output(raw_llm_output)
        self.entities = await self.extract_entities(llm_output_dict)

        return self.entities

if __name__ == "__main__":
    import asyncio

    product_name = "laptop"

    # user_prompt = "Having Display size above 10 inches"
    # user_prompt = "Anything but Apple"
    user_prompt = "I need a laptop under 2000 USD."

    # fetch specification
    agent = EntityExtractionAgent(user_prompt)
    entities = asyncio.run(agent.run(user_prompt, product_name="Laptop"))
    print("Extracted Entities:", entities)