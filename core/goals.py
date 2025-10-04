def has_all(d: dict, keys: set) -> bool:
    return all(k in d and d[k] not in (None, "", [], {}) for k in keys)

GOALS = {
    ("DISCOVERY", None): {
        "mandatory": ["category", "subcategory"],
        "is_done": lambda ws: bool(ws.candidates)
    },
    ("ORDER", None): {
        "mandatory": ["product_id"],
        "is_done": lambda ws: ws.status == "completed"
    }
}

TOOL_GUARDS = {
    "search_products": {
        "required": {"category","subcategory"},
        "allowed_states": {"collecting","presenting"},
        "next_state": "searching"
    }
}


# Per-intent mandatory slots mapping (used by runtime and agents)
MANDATORY_SLOTS = {
    'DISCOVERY': ['subcategory'],
    'ORDER': ['product_id'],
    'PAYMENT': ['order_id'],
    'EXCHANGE': ['order_id'],
    'RETURN': ['order_id']
}
