import logging
from typing import Optional
from aiohttp import web, ClientSession, ClientTimeout
from typing import Any, Self
from .errors import RequestAborted, RequestForward
import asyncio

class Request(web.BaseRequest):
    __slots__ = ()

    def respond(self, response: web.StreamResponse) -> None:
        """
        Immediately sends a response and stops further middleware execution.
        Raises an internal exception that should be caught by the request handler.
        """
        raise RequestAborted(response)


    def forward(self, url: str, request: Self) -> None:
        raise RequestForward(url, request)


class Response(web.Response):
    __slots__ = ()

    def respond(self, response: web.StreamResponse) -> None:
        """
        Immediately sends a response and stops further middleware execution.
        Raises an internal exception that should be caught by the request handler.
        """
        raise RequestAborted(response)


_logger = logging.getLogger(__name__)


class HTTPClient:

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

    def __init__(self, timeout: int = 30):
        self.__session: Optional[ClientSession] = None
        self.timeout = ClientTimeout(total=timeout)

    def clear(self) -> None:
        if self.__session and self.__session.closed:
            self.__session = None

    async def close(self) -> None:
        if self.__session:
            await self.__session.close()

    def _get_session(self) -> ClientSession:
        if self.__session is None or self.__session.closed:
            self.__session = ClientSession(timeout=self.timeout)
        return self.__session

    async def request(self, **kwargs: Any) -> web.Response:
        session = self._get_session()

        raw_headers = kwargs.get("headers")
        if raw_headers is not None:
            kwargs["headers"] = self._filter_headers(
                raw_headers,
                include_host=True
            )

        for tries in range(5):
            try:
                async with session.request(**kwargs) as response:
                    _logger.debug(
                        "%s %s returned %s",
                        response.method,
                        response.url,
                        response.status
                    )

                    response_headers = self._filter_headers(response.headers)
                    response_body = await response.read()

                    return web.Response(
                        status=response.status,
                        reason=response.reason,
                        headers=response_headers,
                        body=response_body
                    )

            except OSError as exc:
                if tries < 4 and exc.errno in {54, 10054}:
                    await asyncio.sleep(1 + tries * 2)
                    continue
                raise

        raise RuntimeError("Unreachable, all retries exhausted")

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