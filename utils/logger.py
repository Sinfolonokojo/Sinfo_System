"""
Logging configuration for the copy trading system.
"""

import logging
import sys
import config


def setup_logger(name: str, level: int = logging.INFO) -> logging.Logger:
    """
    Set up a logger with console output.

    Args:
        name: Logger name (typically the account name).
        level: Logging level. Defaults to INFO.

    Returns:
        Configured logger instance.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    # Avoid duplicate handlers
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        formatter = logging.Formatter(
            config.LOG_FORMAT,
            datefmt=config.LOG_DATE_FORMAT
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    return logger
