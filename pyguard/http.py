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

from typing import Optional, Any, Self, ClassVar, FrozenSet, Dict
from .errors import RequestAborted, RequestForward
from aiohttp import web
import asyncio
import aiohttp
import logging

_logger = logging.getLogger(__name__)

__all__ = ('Request', 'Response', 'HTTPClient')


class Request(web.BaseRequest):
    """Custom request class extending aiohttp.web.BaseRequest with helper methods."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._start_time: Optional[float] = None

    @property
    def start_time(self) -> Optional[float]:
        """
        Timestamp when the request was received.

        Returns
        -------
        Optional[float]
            The time when the request was received, or None if not set.
        """
        return self._start_time

    def respond(self, response: web.StreamResponse) -> None:
        """
        Immediately send a response and abort further middleware processing.

        Parameters
        ----------
        response: web.StreamResponse
            The response object to send immediately.

        Raises
        ------
        RequestAborted
            Raised to stop processing and return the given response.
        """
        raise RequestAborted(response)

    def forward(self, url: str, request: Self) -> None:
        """
        Forward this request to another URL.

        Parameters
        ----------
        url: str
            The target URL to forward the request to.
        request: Request
            The current request instance.

        Raises
        ------
        RequestForward
            Raised to indicate that the request should be forwarded.
        """
        raise RequestForward(url, request)


class Response(web.Response):
    """Custom response class extending aiohttp.web.Response with helper methods."""

    def respond(self, response: web.StreamResponse) -> None:
        """
        Immediately send a response and abort further middleware processing.

        Parameters
        ----------
        response: web.StreamResponse
            The response object to send immediately.

        Raises
        ------
        RequestAborted
            Raised to stop processing and return the given response.
        """
        raise RequestAborted(response)


class HTTPClient:
    """HTTP client for making requests."""

    HOP_BY_HOP_HEADERS: ClassVar[FrozenSet] = frozenset({
        "connection",
        "keep-alive",
        "proxy-authenticate",
        "proxy-authorization",
        "te",
        "trailers",
        "transfer-encoding",
        "upgrade",
    })

    __slots__ = ('connector', '__session', 'proxy', 'proxy_auth', 'http_trace', 'max_ratelimit_timeout')

    def __init__(
            self,
            connector: Optional[aiohttp.BaseConnector] = None,
            *,
            proxy: Optional[str] = None,
            proxy_auth: Optional[aiohttp.BasicAuth] = None,
            http_trace: Optional[aiohttp.TraceConfig] = None
    ) -> None:
        self.connector: Optional[aiohttp.BaseConnector] = connector
        self.__session: Optional[aiohttp.ClientSession] = None

        self.proxy: Optional[str] = proxy
        self.proxy_auth: Optional[aiohttp.BasicAuth] = proxy_auth
        self.http_trace: Optional[aiohttp.TraceConfig] = http_trace

    def clear(self) -> None:
        """Clear the session if it exists and is closed."""
        if self.__session and self.__session.closed:
            self.__session = None

    async def close(self) -> None:
        """Close the active HTTP session."""
        if self.__session:
            await self.__session.close()

    def _get_session(self) -> aiohttp.ClientSession:
        """Get the active ClientSession, creating one if it does not exist or is closed."""
        if self.__session is None or self.__session.closed:
            self.__session = aiohttp.ClientSession(connector=self.connector,
                                                   trace_configs=None if self.http_trace is None else [self.http_trace]
                                                   )
        return self.__session

    async def request(self, **kwargs: Any) -> web.Response:
        """ Send an HTTP request with retries."""
        session = self._get_session()

        raw_headers = kwargs.get("headers")
        if raw_headers is not None:
            kwargs["headers"] = self._filter_headers(raw_headers, include_host=True)

        if self.proxy:
            kwargs['proxy'] = self.proxy
        if self.proxy_auth:
            kwargs['proxy_auth'] = self.proxy_auth

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

    def _filter_headers(self, headers, include_host: bool = False) -> Dict[str, Any]:
        """Remove hop-by-hop headers from the given headers dictionary."""
        excluded = self.HOP_BY_HOP_HEADERS
        if include_host:
            excluded = excluded | {"host"}

        return {k: v for k, v in headers.items() if k.lower() not in excluded}
