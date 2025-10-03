# core/state_factory.py
from typing import Union
from core.states import DiscoveryState, OrderState

def initial_state(intent: str) -> Union[DiscoveryState, OrderState, str]:
    """Return the initial FSM state for a given intent."""
    mapping = {
        "DISCOVERY": DiscoveryState.NEW,
        "ORDER": OrderState.NEW,
        "RETURN": OrderState.NEW,
        "EXCHANGE": OrderState.NEW,
        "PAYMENT": OrderState.NEW,
        # Add other intents as needed
    }
    return mapping.get(intent, "NEW")  # fallback string for unmodeled intents
