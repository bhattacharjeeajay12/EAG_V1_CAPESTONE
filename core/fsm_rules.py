# core/fsm_rules.py
DISCOVERY_TRANSITIONS = {
    "NEW": ["COLLECTING"],
    "COLLECTING": ["READY", "COLLECTING"],  # loop until slots ready
    "READY": ["PROCESSING"],
    "PROCESSING": ["PRESENTING", "FAILED"],
    "PRESENTING": ["AWAITING_DECISION"],
    "AWAITING_DECISION": ["PROCESSING", "CONFIRMING"],
    "CONFIRMING": ["COMPLETED"],
    "FAILED": ["COLLECTING", "COMPLETED"]
}

ORDER_TRANSITIONS = {
    "NEW": ["COLLECTING"],
    "COLLECTING": ["CONFIRMING"],
    "CONFIRMING": ["COMPLETED", "FAILED"],
    "COMPLETED": [],
    "FAILED": []
}

# Unified FSM for a workstream (one source of truth for all workflow types)
WORKSTREAM_TRANSITIONS = {
    "NEW": ["COLLECTING", "FAILED"],
    "COLLECTING": ["READY", "COLLECTING", "FAILED"],        # gather slots / clarifications
    "READY": ["PROCESSING", "PRESENTING", "FAILED"],       # ready to act (execute tool or present)
    "PROCESSING": ["PRESENTING", "AWAITING_DECISION", "FAILED"],
    "PRESENTING": ["AWAITING_DECISION", "COLLECTING", "FAILED"],
    "AWAITING_DECISION": ["PROCESSING", "CONFIRMING", "COLLECTING", "FAILED"],
    "CONFIRMING": ["COMPLETED", "FAILED", "COLLECTING"],   # confirmations, payment, etc.
    "COMPLETED": [],                                       # terminal
    "FAILED": ["COLLECTING", "COMPLETED"],                 # allow recovery or graceful finish
    "PAUSED": ["COLLECTING", "READY", "AWAITING_DECISION"] # resume paths
}
