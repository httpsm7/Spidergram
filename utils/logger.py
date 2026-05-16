"""utils/logger.py — Structured rotating logger."""

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from config.settings import LOGS_DIR


def get_logger(name: str) -> logging.Logger:
    log = logging.getLogger(name)
    if log.handlers:
        return log
    log.setLevel(logging.DEBUG)

    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)-28s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    ch = logging.StreamHandler(sys.stdout)
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)

    fh = RotatingFileHandler(
        LOGS_DIR / f"{name.split('.')[-1]}.log",
        maxBytes=5 * 1024 * 1024, backupCount=3,
    )
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)

    log.addHandler(ch)
    log.addHandler(fh)
    return log


# Root logger for quick imports
logger = get_logger("spidergram")
