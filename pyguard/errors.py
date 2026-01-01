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
from aiohttp import web

__all__ = (
    "PyGuardException",
    "RequestAborted",
    "RequestForward",
    "RequestNotHandled",
)


class PyGuardException(Exception):
    """Base exception for all PyGuard errors."""


class RequestAborted(PyGuardException):
    """Raised when a request is intentionally stopped and a response is immediately returned."""
    def __init__(self, response: web.StreamResponse) -> None:
        self.response: web.StreamResponse = response
        super().__init__(f"Request aborted with response: {response.status}")


class RequestForward(PyGuardException):
    """Raised when a request should be forwarded to another URL or endpoint."""
    __slots__ = ('url', 'request')

    def __init__(self, url: str, request: web.StreamResponse) -> None:
        self.url: str = url
        self.request: web.StreamResponse = request
        super().__init__(f"Request forwarding to: {url}")


class RequestNotHandled(PyGuardException):
    """Raised when a request was neither responded to nor forwarded by the handler."""
    def __init__(self, request: web.BaseRequest, start_time: Optional[float]) -> None:
        self.request: web.BaseRequest = request
        self.start_time: Optional[float] = start_time
        super().__init__(f"Request {request.method} {request.path} did not respond or forward")
