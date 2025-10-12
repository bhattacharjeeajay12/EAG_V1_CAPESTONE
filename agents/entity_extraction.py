from core.llm_client import LLMClient
from prompts.EntityExtraction import get_system_prompt_discovery
from config.constants import SPECIFICATIONS
import json
import ast


class EntityExtractionAgent:
    def __init__(self, user_prompt):
        self.llm_client = LLMClient()
        self.system_prompt = None
        self.user_prompt = user_prompt
        self.entities = []
        self.llm_output = []
        self.available_specs = []
        self.specifications_string = None

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

    async def get_spec_string(self, product_name):
        if product_name not in SPECIFICATIONS:
            raise ValueError(f"Unknown product: {product_name}")
        specs = SPECIFICATIONS.get(product_name.lower(), [])
        self.specifications_string = ", ".join(specs)
        return self.specifications_string

    async def extract_entities(self, llm_output_dict):
        entities = []
        return entities

    async def get_system_prompt(self, phase, product_name="laptop"):
        try:
            if phase == "discovery":
                return get_system_prompt_discovery(product_name, self.specifications_string)
        except Exception as e:
            raise ValueError(f"Error generating system prompt: {e}")

    async def run(self, user_prompt, product_name="laptop", phase="discovery"):
        self.specifications_string = await self.get_spec_string(product_name)
        self.system_prompt = await self.get_system_prompt(phase, product_name)
        raw_llm_output = await self.llm_client.generate(self.system_prompt, user_prompt)
        llm_output_dict = await self.parse_llm_output(raw_llm_output)
        self.entities = await self.extract_entities(llm_output_dict)

        return self.entities

if __name__ == "__main__":
    import asyncio

    # user_prompt = "Anything but Apple"
    user_prompt = "No gaming laptops"

    agent = EntityExtractionAgent(user_prompt)
    entities = asyncio.run(agent.run(user_prompt))
    print("Extracted Entities:", entities)