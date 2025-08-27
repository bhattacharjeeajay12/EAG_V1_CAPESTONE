# core/config.py
from dataclasses import dataclass

# Central thresholds (was in planner.py)
INTENT_THRESHOLDS = {
    "ORDER": 0.7,
    "PAYMENT": 0.7,
    "RETURN": 0.6,
    "EXCHANGE": 0.6,
    "DISCOVERY": 0.5,
    "CHITCHAT": 0.3,
}

@dataclass
class PlannerConfig:
    top_k_present: int = 5  # default items to present in discovery
