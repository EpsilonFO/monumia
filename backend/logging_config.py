"""
Colored logging configuration for PatriAlta backend.

Format: LEVEL (colored) [FILENAME] (violet) message (white)
- INFO  → blue
- DEBUG → green
- ERROR/CRITICAL → red
- WARNING → yellow
"""

import logging
import os

# ANSI color codes
BLUE = "\033[34m"
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
VIOLET = "\033[35m"
WHITE = "\033[97m"
RESET = "\033[0m"

LEVEL_COLORS = {
    logging.DEBUG: GREEN,
    logging.INFO: BLUE,
    logging.WARNING: YELLOW,
    logging.ERROR: RED,
    logging.CRITICAL: RED,
}


class ColoredFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        level_color = LEVEL_COLORS.get(record.levelno, WHITE)
        level_name = f"{level_color}{record.levelname:<8}{RESET}"
        filename = f"{VIOLET}[{record.filename}]{RESET}"
        message = f"{WHITE}{record.getMessage()}{RESET}"
        return f"{level_name} {filename} {message}"


def setup_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()

    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, level, logging.INFO))
    root.handlers.clear()
    root.addHandler(handler)
