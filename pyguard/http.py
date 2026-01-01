from aiohttp import web
import logging
from typing import Optional
from aiohttp import web, ClientSession, ClientTimeout

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


_logger = logging.getLogger(__name__)


class HTTPHandler:
    """Handles HTTP request forwarding."""

    HOP_BY_HOP_HEADERS = frozenset({
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    })

    def __init__(self, target_url: str, timeout: int = 30):
        self.target_url = target_url.rstrip("/")
        self.timeout = ClientTimeout(total=timeout)
        self._session: Optional[ClientSession] = None

    @property
    def session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()
            _logger.debug("HTTP session closed")

    async def forward(self, request: web.Request) -> web.Response:
        target_url = f"{self.target_url}{request.path_qs}"
        _logger.debug(f"Forwarding {request.method} {target_url}")

        # Prepare headers and body
        headers = self._filter_headers(request.headers, include_host=True)
        body = await request.read() if request.can_read_body else None

        try:
            async with self.session.request(
                    method=request.method,
                    url=target_url,
                    headers=headers,
                    data=body,
                    allow_redirects=False
            ) as response:
                response_headers = self._filter_headers(response.headers)
                response_body = await response.read()
                return web.Response(
                    status=response.status,
                    reason=response.reason,
                    headers=response_headers,
                    body=response_body
                )
        except Exception as e:
            _logger.error(f"Error forwarding request to {target_url}: {e}")
            raise

    def _filter_headers(
            self,
            headers,
            include_host: bool = False
    ) -> dict:
        excluded = self.HOP_BY_HOP_HEADERS
        if include_host:
            excluded = excluded | {"host"}

        return {
            k: v for k, v in headers.items()
            if k.lower() not in excluded
        }