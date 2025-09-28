
from __future__ import annotations
import logging
from logging.handlers import RotatingFileHandler
import sys
from pathlib import Path

# DEFAULT_LOG_PATH = Path("/mnt/data/eag_logs")
# DEFAULT_LOG_PATH = Path("/")
DEFAULT_LOG_PATH = Path.home() / "eag_logs"
DEFAULT_LOG_PATH.mkdir(parents=True, exist_ok=True)

def configure_logging(name: str = "eag", level: int = logging.INFO) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger  # already configured

    logger.setLevel(level)

    # console handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(level)
    ch.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)s %(name)s - %(message)s"))

    # rotating file handler
    fh_path = DEFAULT_LOG_PATH / f"{name}.log"
    fh = RotatingFileHandler(fh_path, maxBytes=2_000_000, backupCount=3)
    fh.setLevel(level)
    fh.setFormatter(logging.Formatter("%(asctime)s	%(levelname)s	%(name)s	%(message)s"))

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger.propagate = False
    logger.debug("Logger configured")
    return logger
