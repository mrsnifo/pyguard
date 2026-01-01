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

from typing import TYPE_CHECKING
from .http import HTTPClient
from aiohttp import web
import asyncio

__all__ = ('ClientProxy', )


class ClientProxy:
    """HTTP proxy that forwards requests using a provided HTTP client."""

    if TYPE_CHECKING:
        loop: asyncio.AbstractEventLoop

    def __init__(self, http: HTTPClient) -> None:
        self._http: HTTPClient = http

    async def forward(self, target_url: str, request: web.Request) -> web.Response:
        """Forward an incoming aiohttp request to another URL using the HTTP client."""
        forward_url = f"{target_url}{request.path_qs}"

        body = await request.read() if request.can_read_body else None

        response = await self._http.request(
            method=request.method,
            url=forward_url,
            headers=request.headers,
            data=body,
            allow_redirects=False,
        )
        return response
