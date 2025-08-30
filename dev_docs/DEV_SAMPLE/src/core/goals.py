
from __future__ import annotations
from typing import Dict, Any
from .conversation_history import Workstream

def nonempty(v): return v not in (None,"",[],{})

GOALS: Dict[tuple, Dict[str, Any]] = {
    ("DISCOVERY", None): {
        "mandatory": ["category","subcategory"],
        "is_done": lambda ws: ws.status == "completed" or bool(ws.slots.get("selected_product_id"))
    },
    ("DISCOVERY", "compare"): {
        "mandatory": ["category","subcategory"],
        "is_done": lambda ws: bool(ws.compare.get("left") and ws.compare.get("right"))
    },
    ("ORDER", "place_order"): {
        "mandatory": ["product_id","shipping_address","payment_method"],
        "is_done": lambda ws: ws.status == "completed"
    },
}

TOOL_GUARDS = {
  "search_products": {
    "required": {"category","subcategory"},
    "allowed_states": {"collecting","presenting"},
    "next_state": "searching"
  },
  "build_compare_view": {
    "required": {"comparison_items"},
    "allowed_states": {"collecting","presenting"},
    "next_state": "comparing"
  },
  "recommend_products": {
    "required": {"preferences"},
    "allowed_states": {"collecting","presenting"},
    "next_state": "presenting"
  },
  "fetch_specs": {
    "required": {"selected_product_id"},
    "allowed_states": {"presenting","comparing"},
    "next_state": "presenting"
  }
}

def has_all(src: dict, keys: set[str]) -> bool:
    return all(k in src and nonempty(src[k]) for k in keys)
