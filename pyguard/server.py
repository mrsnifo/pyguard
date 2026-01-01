from __future__ import annotations
from typing import Callable, Any
from .protocol import RequestHandler
from aiohttp import web_server
from typing import TYPE_CHECKING
import asyncio
if TYPE_CHECKING:
    from .proxy import Proxy


class Server(web_server.Server):

    __slots__ = ('loop', 'dispatch', 'proxy')

    def __init__(self,
                 dispatch: Callable[..., Any],
                 proxy: Proxy,
                 *args, **kwargs
                 ):
        self.dispatch = dispatch
        self.proxy = proxy
        super().__init__(*args, **kwargs)

    def __call__(self) -> RequestHandler:
        return RequestHandler(self, loop=self.proxy.loop, **self._kwargs)