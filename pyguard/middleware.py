from aiohttp import web
from typing import Callable, Awaitable, Generator
from aiohttp.typedefs import Handler
from aiohttp.web_app import Application
from aiohttp.web_request import Request
from aiohttp.web_response import StreamResponse

MiddlewareType = Callable[
    [Application, Callable[[Request], Awaitable[StreamResponse]]],
    Awaitable[Callable[[Request], Awaitable[StreamResponse]]]
]

class Middleware:
    async def before(self, request: Request) -> None:
        print("BEFORE:", request.method, request.path)

    async def after(self, request: Request, response: StreamResponse) -> None:
        print("AFTER:", response.status)

    async def middleware(self, _, handler: Handler) -> Handler:
        async def wrapped(request: Request) -> StreamResponse:
            await self.before(request)
            try:
                response = await handler(request)
            except web.HTTPException as exc:
                await self.after(request, exc)
                raise
            await self.after(request, response)
            return response
        return wrapped

    def __iter__(self) -> Generator[MiddlewareType, None, None]:
        yield self.middleware
