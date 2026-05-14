"""
logger.py
=========
Enterprise Unified Logging Architecture.

Implements a strictly configured logger factory providing standardized log formats
across all modules, ensuring compliance with production log aggregation pipelines.
"""

import logging
import sys
from logging import Logger

# Absolute logging format compliant with corporate log indexes (Timestamp | Level | Module | Line | Msg)
DEFAULT_LOG_FORMAT = (
    "[%(asctime)s.%(msecs)03d] [%(levelname)s] [%(name)s:%(lineno)d] - %(message)s"
)
DEFAULT_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


def get_logger(module_name: str, log_level: int = logging.INFO) -> Logger:
    """
    Builds and returns an enterprise-configured Logger instance.

    Args:
        module_name (str): The fully qualified __name__ of the importing module.
        log_level (int): Desired logging threshold (defaults to INFO).

    Returns:
        logging.Logger: An active, thread-safe logging interface.
    """
    # Encapsulate under our system scope
    qualified_name = f"psl.{module_name}"
    logger = logging.getLogger(qualified_name)
    
    # Prevent handler duplication if logger exists
    if logger.hasHandlers():
        return logger

    logger.setLevel(log_level)
    logger.propagate = False

    # Create clean standard output channel
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)

    # Apply uniform corporate layout
    formatter = logging.Formatter(
        fmt=DEFAULT_LOG_FORMAT,
        datefmt=DEFAULT_DATE_FORMAT
    )
    console_handler.setFormatter(formatter)
    
    logger.addHandler(console_handler)
    
    return logger
