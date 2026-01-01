from __future__ import annotations

import logging
from aiohttp import web

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .http import HTTPClient

_logger = logging.getLogger(__name__)

class Proxy:
    def __init__(self, http: HTTPClient):
        self._http = http

    async def forward(self, target_url: str, request: web.Request) -> web.Response:
        target_url = f"{target_url}{request.path_qs}"

        _logger.debug(
            "Forwarding HTTP request: %s %s",
            request.method,
            request.path_qs,
        )

        body = await request.read() if request.can_read_body else None

        return await self._http.request(
            method=request.method,
            url=target_url,
            headers=request.headers,
            data=body,
            allow_redirects=False,
        )
