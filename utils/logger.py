import logging
import json
import sys
from datetime import datetime
from typing import Any, Dict, Optional


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        base: Dict[str, Any] = {
            "time": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        # Include common structured fields if provided via extra
        for key in ("agent", "event", "why", "data", "session_id", "caller", "callee"):
            if hasattr(record, key):
                base[key] = getattr(record, key)
        return json.dumps(base, ensure_ascii=False)


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger
    logger.setLevel(logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logger.addHandler(handler)
    logger.propagate = False
    return logger


def log_decision(logger: logging.Logger, agent: str, event: str, why: str, data: Optional[Dict[str, Any]] = None, session_id: Optional[str] = None) -> None:
    extra = {
        "agent": agent,
        "event": event,
        "why": why,
        "data": data or {},
        "session_id": session_id,
    }
    logger.info(event, extra=extra)
