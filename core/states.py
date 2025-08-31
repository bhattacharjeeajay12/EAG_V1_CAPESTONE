# core/states.py
from enum import Enum

class DiscoveryState(Enum):
    NEW = "new"
    COLLECTING = "collecting"
    READY = "ready"
    PROCESSING = "processing"
    PRESENTING = "presenting"
    AWAITING_DECISION = "awaiting_decision"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"


class OrderState(Enum):
    NEW = "new"
    COLLECTING = "collecting"
    CONFIRMING = "confirming"
    COMPLETED = "completed"
    FAILED = "failed"
