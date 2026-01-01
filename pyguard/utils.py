from __future__ import annotations
from typing import Optional
import logging

__all__ = (
    'setup_logging',
)

def setup_logging(
    handler: Optional[logging.Handler] = None,
    level: Optional[int] = None,
    root: bool = True
) -> None:
    logging.getLogger("aiohttp.access").setLevel(logging.WARNING)

    logger = logging.getLogger() if root else logging.getLogger(__name__.split('.')[0])
    logger.setLevel(level if level is not None else logging.INFO)

    if logger.hasHandlers():
        logger.handlers.clear()

    handler = handler or logging.StreamHandler()
    handler.setFormatter(logging.Formatter(
        '[{asctime}] [{levelname}] {name}: {message}',
        '%Y-%m-%d %H:%M:%S',
        style='{'
    ))
    logger.addHandler(handler)

    logging.captureWarnings(True)
