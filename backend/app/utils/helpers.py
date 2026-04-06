"""
helpers.py
----------
Shared utility functions used across routes and services.
"""

import time
import uuid
from functools import wraps
from typing import Any, Callable

from loguru import logger

from app.schemas.models import PredictionLabel, SeverityLevel


def get_severity(probability: float) -> SeverityLevel:
    """
    Map attack probability to a human-readable severity level.

    Args:
        probability: LSTM output probability (0.0 – 1.0)

    Returns:
        SeverityLevel enum value
    """
    if probability >= 0.90:
        return SeverityLevel.CRITICAL
    elif probability >= 0.75:
        return SeverityLevel.HIGH
    elif probability >= 0.50:
        return SeverityLevel.MEDIUM
    else:
        return SeverityLevel.LOW


def get_label(probability: float, threshold: float = 0.5) -> PredictionLabel:
    """Return ATTACK or NORMAL based on threshold."""
    return PredictionLabel.ATTACK if probability >= threshold else PredictionLabel.NORMAL


def generate_id() -> str:
    """Generate a short unique ID for predictions and reports."""
    return str(uuid.uuid4())


def timer_ms() -> Callable:
    """
    Decorator that logs execution time in milliseconds.

    Usage:
        @timer_ms()
        def my_func(): ...
    """
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0     = time.perf_counter()
            result = await func(*args, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug(f"{func.__name__} completed in {elapsed:.2f} ms")
            return result

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            t0     = time.perf_counter()
            result = func(*args, **kwargs)
            elapsed = (time.perf_counter() - t0) * 1000
            logger.debug(f"{func.__name__} completed in {elapsed:.2f} ms")
            return result

        import asyncio
        return async_wrapper if asyncio.iscoroutinefunction(func) else sync_wrapper

    return decorator


def safe_divide(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide without ZeroDivisionError."""
    return numerator / denominator if denominator != 0 else default


def clamp(value: float, min_val: float = 0.0, max_val: float = 1.0) -> float:
    """Clamp a float between min and max."""
    return max(min_val, min(max_val, value))
