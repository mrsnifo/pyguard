from aiohttp import web
from typing import Callable, Awaitable, Generator
from aiohttp.typedefs import Handler
from aiohttp.web_app import Application
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse
from .state import ConnectionState

MiddlewareType = Callable[
    [Application, Callable[[Request], Awaitable[StreamResponse]]],
    Awaitable[Callable[[Request], Awaitable[StreamResponse]]]
]

class Middleware:

    def __init__(self, state: ConnectionState):
        self._state = state

    async def middleware(self, _, handler: Handler) -> Handler:
        async def wrapped(request: Request) -> StreamResponse:
            await self._state.on_request_start(request)
            try:
                response = await handler(request)
            except web.HTTPException as exc:
                await self._state.on_request_error(request, exc)
                raise
            await self._state.on_request_end(request, response)
            return response
        return wrapped

    def __iter__(self) -> Generator[MiddlewareType, None, None]:
        yield self.middleware
