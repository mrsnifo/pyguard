"""
The MIT License (MIT)

Copyright (c) 2026-present mrsnifo

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

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
    """Configure logging for the application."""
    # Reduce verbosity of aiohttp access logs
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
