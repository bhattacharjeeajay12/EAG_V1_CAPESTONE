
from __future__ import annotations
from dataclasses import dataclass

INTENT_THRESHOLDS = {
    "DISCOVERY": 0.6,
    "ORDER": 0.6,
    "RETURN": 0.6,
    "EXCHANGE": 0.6,
    "PAYMENT": 0.6,
    "CHITCHAT": 0.5,
}

@dataclass
class PlannerConfig:
    max_present_items: int = 20
    ask_one_slot_at_a_time: bool = True
