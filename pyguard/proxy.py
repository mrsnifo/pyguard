import asyncio
import logging
from aiohttp import web, ClientSession, ClientTimeout, WSMsgType
from typing import Optional

_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class Proxy:
    """Reverse proxy supporting HTTP and WebSocket, returns web.Response."""

    def __init__(self, target_url: str, timeout: int = 30):
        self.target_url = target_url.rstrip("/")
        self.timeout = ClientTimeout(total=timeout)
        self._session: Optional[ClientSession] = None

    @property
    def session(self) -> ClientSession:
        if self._session is None or self._session.closed:
            self._session = ClientSession(timeout=self.timeout)
        return self._session

    async def close(self) -> None:
        if self._session and not self._session.closed:
            await self._session.close()

    @staticmethod
    def is_websocket(request: web.Request) -> bool:
        return (
            request.headers.get("Upgrade", "").lower() == "websocket"
            and "upgrade" in request.headers.get("Connection", "").lower()
        )

    async def forward(self, request: web.Request) -> web.Response:
        """Forward HTTP request and return a web.Response."""
        if self.is_websocket(request):
            raise ValueError("WebSocket requests should use forward_ws()")

        target = f"{self.target_url}{request.path_qs}"
        headers = self._prepare_headers(request.headers)
        body = await request.read() if request.can_read_body else None

        async with self.session.request(
                method=request.method,
                url=target,
                headers=headers,
                data=body,
                allow_redirects=False
        ) as resp:
            resp_headers = self._prepare_response_headers(resp.headers)
            proxy_response = web.Response(
                status=resp.status,
                reason=resp.reason,
                headers=resp_headers,
                body=await resp.read()
            )
            return proxy_response

    async def _forward_ws(self, request: web.Request) -> web.WebSocketResponse:
        target = f"{self.target_url}{request.path_qs}"
        _logger.debug(f"Forwarding WebSocket: {target}")

        async with self.session.ws_connect(target) as ws_client:
            ws_server = web.WebSocketResponse()
            await ws_server.prepare(request)

            async def client_to_server():
                async for msg in ws_client:
                    if msg.type == WSMsgType.TEXT:
                        await ws_server.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_server.send_bytes(msg.data)
                    elif msg.type == WSMsgType.CLOSE:
                        await ws_server.close()
                        break

            async def server_to_client():
                async for msg in ws_server:
                    if msg.type == WSMsgType.TEXT:
                        await ws_client.send_str(msg.data)
                    elif msg.type == WSMsgType.BINARY:
                        await ws_client.send_bytes(msg.data)
                    elif msg.type == WSMsgType.CLOSE:
                        await ws_client.close()
                        break

            await asyncio.gather(client_to_server(), server_to_client())
            return ws_server

    # --- Header helpers ---
    def _prepare_headers(self, headers) -> dict:
        hop_by_hop = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
            "host",
        }
        return {k: v for k, v in headers.items() if k.lower() not in hop_by_hop}

    def _prepare_response_headers(self, headers) -> dict:
        hop_by_hop = {
            "connection",
            "keep-alive",
            "proxy-authenticate",
            "proxy-authorization",
            "te",
            "trailers",
            "transfer-encoding",
            "upgrade",
        }
        return {k: v for k, v in headers.items() if k.lower() not in hop_by_hop}
