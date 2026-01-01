from aiohttp.web import BaseRequest, StreamResponse
from typing import Optional

# Internal exception used to short-circuit middleware
class _RespondNow(Exception):
    __slots__ = ("response",)

    def __init__(self, response: StreamResponse):
        self.response = response

class CustomRequest:
    __slots__ = ("_req",)

    def __init__(self, request: BaseRequest):
        self._req = request

    def respond(self, response: StreamResponse) -> None:
        """
        Immediately sends a response and stops further middleware execution.
        Raises an internal exception that should be caught by the request handler.
        """
        raise _RespondNow(response)

    def __getattr__(self, name):
        # Delegate any other attribute access to the underlying aiohttp request
        return getattr(self._req, name)
