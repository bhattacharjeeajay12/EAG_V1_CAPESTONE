from config.specifications import SPECIFICATIONS
from dataclasses import dataclass, field
from typing import Dict, List, Any
from core.states import DiscoveryState, OrderState
from typing import Union

@dataclass
class Workstream:
    id: str
    type: str  # DISCOVERY | ORDER | RETURN | EXCHANGE | PAYMENT | CHITCHAT
    status: Union[DiscoveryState, OrderState, str]
    skip_specifications: bool = False
    slots: Dict[str, Any] = field(default_factory=dict)
    candidates: List[Dict[str, Any]] = field(default_factory=list)
    compare: Dict[str, Any] = field(default_factory=lambda: {"left": None, "right": None})
    satisfaction: float = 0.0

    def update_slots(self, new_entities: dict):
        for k, v in new_entities.items():
            if k == "specifications" and isinstance(v, dict):
                self.slots.setdefault("specifications", {}).update(v)
            else:
                self.slots[k] = v

    def missing_specifications(self) -> list:
        """Return list of unfilled optional specs for current subcategory."""
        if self.skip_specifications:
            return []

        subcat = self.slots.get("subcategory")
        if not subcat:
            return []

        available_specs = SPECIFICATIONS.get(subcat, [])
        specs = self.slots.get("specifications", {})
        return [s for s in available_specs if s not in specs]