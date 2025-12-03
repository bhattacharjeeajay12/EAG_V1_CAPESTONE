from config.enums import PlanGeneratorAgents as DPA
from config.enums import ToolNames as TN

DISCOVERY_WS_AGENT_NAMES = [DPA.ENTITY_EXTRACTION.value, DPA.QUERY_BUILDER_EXECUTOR.value, DPA.SUMMARIZER.value]
DISCOVERY_WS_TOOLS_NAMES = [TN.GET_ALL_BRANDS_NAMES.value, TN.GET_ALL_SPECIFICATIONS.value]

ALL_AGENT_REGISTRY = [
    {
        "AGENT_NAME": DPA.ENTITY_EXTRACTION.value,
        "DESCRIPTION": "This agent Extracts structured filters (key, value, unit, operator) from a user’s sentence. For Example, example -1 - I need something under 2000 USD, here the extracted output will be {{key:price,value:[0,2000],unit:USD,operator:BETWEEN}}. example -2 - At least 8GB RAM, here the output will be {{key:ram,value:[8,null],unit:gigabytes,operator:BETWEEN}}. example - 3 - Anything but Apple, here the output will be {{key:brand,value:apple,operator:NOT IN}}."
    },
    {
        "AGENT_NAME": DPA.QUERY_BUILDER_EXECUTOR.value,
        "DESCRIPTION": "This agent builds and executes queries based on extracted filters to retrieve relevant items from the database."
    },
    {
        "AGENT_NAME": DPA.SUMMARIZER.value,
        "DESCRIPTION": "This agent summarizes the retrieved items into a concise format for user presentation."
    }
]

ALL_TOOL_REGISTRY = [
    {
        "TOOL_NAME": TN.GET_ALL_BRANDS_NAMES.value,
        "DESCRIPTION": "Fetches a list of all available brand names from the product database."
    },
    {
        "TOOL_NAME": TN.GET_ALL_SPECIFICATIONS.value,
        "DESCRIPTION": "Fetches all specifications for a given subcategory from the product database."
    }
]

def get_discovery_agents_registry() -> list[dict]:
    """ Returns the registry of all discovery workstream agents. """
    discovery_agents_registry = []
    for agent in ALL_AGENT_REGISTRY:
        if agent["AGENT_NAME"] in DISCOVERY_WS_AGENT_NAMES:
            discovery_agents_registry.append(agent)
    return discovery_agents_registry

def get_discovery_tools_registry() -> list[dict]:
    """ Returns the registry of all discovery workstream tools. """
    discovery_tools_registry = []
    for tool in ALL_TOOL_REGISTRY:
        if tool["TOOL_NAME"] in DISCOVERY_WS_TOOLS_NAMES:
            discovery_tools_registry.append(tool)
    return discovery_tools_registry
