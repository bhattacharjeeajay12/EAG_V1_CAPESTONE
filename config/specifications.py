# core/specifications.py
from core.agents import Agents

SPECIFICATIONS = {
    "laptop": ["ram", "storage", "processor", "display"],
    "tablet": ["storage", "battery", "screen_size"],
    "phone": ["storage", "camera", "battery", "color"],
}

CATEGORIES = {
    "electronics": ["laptop", "smartphone", "earphone", "graphic", "tablet", "camera"],
    "sports": ["yoga mat", "dumbbells", "cricket bat", "basketball", "treadmill"]
}

MANDATORY_SLOTS = {
    Agents.DISCOVERY: ["subcategory"],
    Agents.ORDER: ["subcategory"],
    Agents.PAYMENT: ["order_id"],
    Agents.EXCHANGE: ["order_id"],
    Agents.RETURN: ["order_id"],

}