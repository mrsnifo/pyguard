from aiohttp import web

class RequestAborted(Exception):
    __slots__ = ("response",)

    def __init__(self, response: web.StreamResponse):
        self.response = response


class Request(web.BaseRequest):
    __slots__ = ('request',)

    def respond(self, response: web.StreamResponse) -> None:
        """
        Immediately sends a response and stops further middleware execution.
        Raises an internal exception that should be caught by the request handler.
        """
        raise RequestAborted(response)

    def __repr__(self):
        return repr(self.request)


class Response(web.Response):
    """
    Subclass of aiohttp.web.Response with `respond()` helper.
    """

    def respond(self, response: web.StreamResponse) -> None:
        """
        Immediately sends a response and stops further middleware execution.
        Raises an internal exception that should be caught by the request handler.
        """
        raise RequestAborted(response)

    def __repr__(self):
        return super().__repr__()
