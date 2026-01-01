import logging
from aiohttp import web
from typing import Union

from .http import HTTPHandler
from .gateway import WebSocketHandler

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class Proxy:

    def __init__(self, target_url: str, timeout: int = 30):
        self.target_url = target_url.rstrip("/")
        self.http_handler = HTTPHandler(target_url, timeout)
        self.ws_handler = WebSocketHandler(target_url, timeout)
        _logger.info(f"Proxy initialized for target: {target_url}")

    async def forward(
            self,
            request: web.Request
    ) -> Union[web.Response, web.WebSocketResponse]:
        if self.ws_handler.is_websocket_request(request):
            _logger.debug(f"Handling WebSocket request: {request.path}")
            return await self.ws_handler.forward(request)
        else:
            _logger.debug(f"Handling HTTP request: {request.method} {request.path}")
            return await self.http_handler.forward(request)

    async def close(self) -> None:
        """Close all active sessions."""
        _logger.info("Closing proxy sessions...")
        await self.http_handler.close()
        await self.ws_handler.close()
        _logger.info("Proxy sessions closed")
