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
    """Base exception for pyguard errors."""
    pass

class RequestAborted(PyGuardException):
    def __init__(self, response: web.StreamResponse) -> None:
        self.response: web.StreamResponse = response
        super().__init__(f"Request aborted with response: {response.status}")

class RequestForward(PyGuardException):
    __slots__ = ('url', 'request')

    def __init__(self, url: str, request: web.StreamResponse) -> None:
        self.url: str = url
        self.request: web.StreamResponse = request
        super().__init__(f"Request forwarding to: {url}")

class RequestNotHandled(PyGuardException):
    """Raised when a request was neither responded to nor forwarded."""

    def __init__(self, request: web.BaseRequest, start_time: Optional[float]) -> None:
        self.request: web.BaseRequest = request
        self.start_time: Optional[float] = start_time
        super().__init__(f"Request {request.method} {request.path} did not respond or forward")