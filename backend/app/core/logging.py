"""
logging.py
----------
Loguru-based structured logging configuration.
Writes to both stderr (coloured) and a rotating log file.
"""

import sys
from pathlib import Path

from loguru import logger

from app.core.config import get_settings

BASE_DIR = Path(__file__).resolve().parents[3]   # backend/
LOG_DIR  = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)


def setup_logging() -> None:
    """
    Configure Loguru sinks:
      1. Stderr  — coloured, level from settings
      2. Log file — JSON-structured, rotating 20 MB, 10 days retention
    Call once at application startup (inside lifespan).
    """
    settings = get_settings()

    # Remove the default Loguru handler:
    logger.remove()

    # ── Sink 1: stderr (human-readable, coloured) ─────────────────
    logger.add(
        sys.stderr,
        level=settings.log_level,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
        backtrace=True,
        diagnose=settings.debug,
    )

    # ── Sink 2: rotating file (JSON structured) ───────────────────
    logger.add(
        LOG_DIR / "app.log",
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {name}:{line} | {message}",
        rotation="20 MB",
        retention="10 days",
        compression="zip",
        backtrace=True,
        diagnose=False,
        enqueue=True,           # async-safe: writes on a separate thread
    )

    logger.info(f"Logging initialised — level={settings.log_level}")
