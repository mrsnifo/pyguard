from .protocol import RequestHandler
from aiohttp import web_server

class Server(web_server.Server):
    def __call__(self) -> RequestHandler:
        return RequestHandler(self, loop=self._loop, **self._kwargs)