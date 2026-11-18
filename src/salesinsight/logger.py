"""Logging setup: messages go to the console and to logs/salesinsight.log."""

from __future__ import annotations

import logging

from salesinsight import config

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(name: str) -> logging.Logger:
    """Return a logger that writes to the console and to the log file.

    Calling this many times with the same name is safe: handlers are
    added only once, so messages are never printed twice.

    Usage:
        from salesinsight.logger import get_logger
        logger = get_logger(__name__)
        logger.info("Loaded %d rows", len(df))
    """
    logger = logging.getLogger(name)

    if logger.handlers:  # already set up
        return logger

    logger.setLevel(config.LOG_LEVEL)
    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    config.LOGS_DIR.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(config.LOG_FILE, encoding="utf-8")
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    logger.propagate = False  # stop duplicate messages from the root logger
    return logger
