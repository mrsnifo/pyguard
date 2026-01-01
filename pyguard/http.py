from aiohttp.web import BaseRequest, StreamResponse

class RequestAborted(Exception):
    __slots__ = ("response",)

    def __init__(self, response: StreamResponse):
        self.response = response

class Request:
    __slots__ = ("_req",)

    def __init__(self, request: BaseRequest):
        self._req = request

    def respond(self, response: StreamResponse) -> None:
        """
        Immediately sends a response and stops further middleware execution.
        Raises an internal exception that should be caught by the request handler.
        """
        raise RequestAborted(response)

    def __getattr__(self, name):
        return getattr(self._req, name)
