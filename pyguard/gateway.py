"""WebSocket connection forwarding handler."""
import asyncio
import logging
from typing import Optional
from aiohttp import web, ClientSession, ClientTimeout, WSMsgType

_logger = logging.getLogger(__name__)


class WebSocketHandler:
    """Handles WebSocket connection forwarding."""

    def __init__(self, target_url: str, timeout: int = 30):
        """
        Initialize WebSocket handler.

        Args:
            target_url: Base URL of the target server
            timeout: Connection timeout in seconds
        """
        self.target_url = target_url.rstrip("/")
        self.timeout = ClientTimeout(total=timeout)
        self._session: Optional[ClientSession] = None

    @property
    def session(self) -> ClientSession:
        """Get or create aiohttp ClientSession."""
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        """Close the WebSocket session."""
        if self._session and not self._session.closed:
            await self._session.close()
            _logger.debug("WebSocket session closed")

    @staticmethod
    def is_websocket_request(request: web.Request) -> bool:
        """
        Check if the request is a WebSocket upgrade request.

        Args:
            request: The incoming request

        Returns:
            bool: True if this is a WebSocket request
        """
        upgrade = request.headers.get("Upgrade", "").lower()
        connection = request.headers.get("Connection", "").lower()
        return upgrade == "websocket" and "upgrade" in connection

    async def forward(self, request: web.Request) -> web.WebSocketResponse:
        """
        Forward a WebSocket connection to the target server.

        Args:
            request: The incoming WebSocket request

        Returns:
            web.WebSocketResponse: The WebSocket response

        Raises:
            Exception: If the WebSocket forwarding fails
        """
        target_url = f"{self.target_url}{request.path_qs}"
        target_url = target_url.replace("http://", "ws://").replace("https://", "wss://")

        _logger.debug(f"Forwarding WebSocket connection to {target_url}")

        try:
            async with self.session.ws_connect(target_url) as ws_client:
                # Prepare WebSocket response to client
                ws_server = web.WebSocketResponse()
                await ws_server.prepare(request)

                # Create bidirectional forwarding tasks
                tasks = [
                    self._forward_client_to_server(ws_client, ws_server),
                    self._forward_server_to_client(ws_server, ws_client)
                ]

                # Run both forwarding tasks concurrently
                await asyncio.gather(*tasks, return_exceptions=True)

                return ws_server

        except Exception as e:
            _logger.error(f"WebSocket forwarding error: {e}")
            raise

    async def _forward_client_to_server(
            self,
            ws_client,
            ws_server: web.WebSocketResponse
    ) -> None:
        try:
            async for msg in ws_client:
                if msg.type == WSMsgType.TEXT:
                    await ws_server.send_str(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    await ws_server.send_bytes(msg.data)
                elif msg.type == WSMsgType.CLOSE:
                    _logger.debug("Target server closed WebSocket connection")
                    await ws_server.close()
                    break
                elif msg.type == WSMsgType.ERROR:
                    _logger.error(f"WebSocket error from server: {msg.data}")
                    break
        except Exception as e:
            _logger.error(f"Error forwarding from server to client: {e}")
            await ws_server.close()

    async def _forward_server_to_client(
            self,
            ws_server: web.WebSocketResponse,
            ws_client
    ) -> None:
        try:
            async for msg in ws_server:
                if msg.type == WSMsgType.TEXT:
                    await ws_client.send_str(msg.data)
                elif msg.type == WSMsgType.BINARY:
                    await ws_client.send_bytes(msg.data)
                elif msg.type == WSMsgType.CLOSE:
                    _logger.debug("Client closed WebSocket connection")
                    await ws_client.close()
                    break
                elif msg.type == WSMsgType.ERROR:
                    _logger.error(f"WebSocket error from client: {msg.data}")
                    break
        except Exception as e:
            _logger.error(f"Error forwarding from client to server: {e}")
            await ws_client.close()