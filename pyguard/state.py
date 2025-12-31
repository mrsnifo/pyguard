import logging
from aiohttp import web
from .proxy import Proxy

_logger = logging.getLogger(__name__)


class ConnectionState:
    def __init__(self, app, proxy: Proxy):
        self.app = app
        self.proxy = proxy
        self._active_requests = 0
        self._total_requests = 0

    @property
    def active_requests(self):
        return self._active_requests

    @property
    def total_requests(self):
        return self._total_requests

    async def on_request_start(self, request):
        self._active_requests += 1
        self._total_requests += 1
        _logger.debug(f"Request started: {request.method} {request.path}")

        if not self.proxy:
            raise web.HTTPNotFound(text="No proxy configured")

        return await self.proxy.forward(request)

    async def on_request_end(self, request, response):
        self._active_requests -= 1
        _logger.debug(f"Request completed: {request.method} {request.path} -> {response.status}")

    async def on_request_error(self, request, error):
        self._active_requests -= 1
        if not isinstance(error, web.HTTPException):
            _logger.warning(f"Request failed: {request.method} {request.path} -> {error}")