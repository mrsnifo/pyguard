import asyncio
from typing import Optional, Type, Any, Callable, Awaitable, Tuple
from aiohttp.web_exceptions import HTTPException, HTTPInternalServerError
import warnings

from aiohttp.abc import AbstractAccessLogger, AbstractStreamWriter
from aiohttp.http_parser import RawRequestMessage
from aiohttp.web import Application, Request, Response
from aiohttp.web_log import AccessLogger
from aiohttp.web_protocol import RequestHandler
from aiohttp.web_request import BaseRequest
from aiohttp.web_response import StreamResponse
from aiohttp.web_server import Server
from aiohttp import web, StreamReader


class App(Application):

    def _make_handler(
            self,
            *,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            access_log_class: Type[AbstractAccessLogger] = AccessLogger,
            **kwargs: Any,
    ) -> Server:

        if not issubclass(access_log_class, AbstractAccessLogger):
            raise TypeError(
                "access_log_class must be subclass of "
                "aiohttp.abc.AbstractAccessLogger, got {}".format(access_log_class)
            )

        self._set_loop(loop)
        self.freeze()

        kwargs["debug"] = self._debug
        kwargs["access_log_class"] = access_log_class
        if self._handler_args:
            for k, v in self._handler_args.items():
                kwargs[k] = v

        server = Server(
            self._handle,  # type: ignore[arg-type]
            request_factory=self._make_request,
            loop=self._loop,
            **kwargs,
        )
        # noinspection PyProtectedMember
        server.__call__ = lambda: RequestHandler(server, loop=server._loop, **server._kwargs)
        return server


class Ser(Server):


    def __call__(self) -> RequestHandler:
        try:
            return R(self, loop=self._loop, **self._kwargs)
        except TypeError:
            # Failsafe creation: remove all custom handler_args
            kwargs = {
                k: v
                for k, v in self._kwargs.items()
                if k in ["debug", "access_log_class"]
            }
            return RequestHandler(self, loop=self._loop, **kwargs)


class R(RequestHandler):

    async def _handle_request(
        self,
        request: BaseRequest,
        start_time: Optional[float],
        request_handler: Callable[[BaseRequest], Awaitable[StreamResponse]],
    ) -> Tuple[StreamResponse, bool]:

        self._request_in_progress = True
        try:
            try:
                self._current_request = request
                resp = await request_handler(request)

            finally:
                self._current_request = None
        except HTTPException as exc:
            resp = exc
            resp, reset = await self.finish_response(request, resp, start_time)
        except asyncio.CancelledError:
            raise
        except asyncio.TimeoutError as exc:
            self.log_debug("Request handler timed out.", exc_info=exc)
            resp = self.handle_error(request, 504)
            resp, reset = await self.finish_response(request, resp, start_time)
        except Exception as exc:
            resp = self.handle_error(request, 500, exc)
            resp, reset = await self.finish_response(request, resp, start_time)
        else:
            # Deprecation warning (See #2415)
            if getattr(resp, "__http_exception__", False):
                warnings.warn(
                    "returning HTTPException object is deprecated "
                    "(#2415) and will be removed, "
                    "please raise the exception instead",
                    DeprecationWarning,
                )

            resp, reset = await self.finish_response(request, resp, start_time)
        finally:
            self._request_in_progress = False
            if self._handler_waiter is not None:
                self._handler_waiter.set_result(None)

        return resp, reset

# Route handlers
async def hello(request: Request) -> Response:
    return Response(text="Hello, World!")


async def echo(request: Request) -> Response:
    data = await request.text()
    return Response(text=f"Echo: {data}")


async def json_handler(request: Request) -> Response:
    return web.json_response({
        "status": "success",
        "message": "Custom App is working!",
        "path": request.path
    })


def main():
    # Create custom app instance
    app = App()

    # Run the app
    print("Starting server on http://localhost:8080")
    print("Available routes:")
    print("  - GET  http://localhost:8080/")
    print("  - GET  http://localhost:8080/json")
    print("  - POST http://localhost:8080/echo")

    web.run_app(app, host='localhost', port=8080)


if __name__ == '__main__':
    main()