from __future__ import annotations

from .protocol import RequestHandler
from aiohttp import web_server


class Server(web_server.Server):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)



    def __call__(self) -> RequestHandler:
        return RequestHandler(self, loop=self._loop, **self._kwargs)