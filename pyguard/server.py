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

from .protocol import RequestHandler
from typing import Callable, Any
from aiohttp import web_server
from .proxy import ClientProxy

__all__ = ('Server',)


class Server(web_server.Server):
    """Custom aiohttp server that integrates request dispatching and proxy support."""

    __slots__ = ('loop', 'dispatch', 'proxy')

    def __init__(
        self,
        dispatch: Callable[..., Any],
        proxy: ClientProxy,
        *args,
        **kwargs
    ) -> None:
        self.dispatch: Callable[..., Any] = dispatch
        self.proxy: ClientProxy = proxy
        super().__init__(*args, **kwargs)

    def __call__(self) -> RequestHandler:
        """
        Return a new RequestHandler instance for handling incoming requests.

        Returns
        -------
        RequestHandler
            A request handler bound to this server and the proxy's event loop.
        """
        return RequestHandler(self, loop=self.proxy.loop, **self._kwargs)
