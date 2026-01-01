from __future__ import annotations

import asyncio
from aiohttp.web import Response

from typing import Optional, Type, Any
from aiohttp.abc import AbstractAccessLogger
from aiohttp.web import Application, AppRunner, TCPSite, BaseRequest
from aiohttp.web_log import AccessLogger
from typing import Callable
from types import TracebackType
from .server import Server
import logging
from . import utils

_logger = logging.getLogger(__name__)

class _LoopSentinel:
    """Sentinel class to handle loop access before app initialization."""
    __slots__ = ()

    def __getattr__(self, attr: str) -> None:
        raise AttributeError(
            "Cannot access 'loop' before the app is fully initialized. "
            "Run inside an asynchronous context."
        )


_loop: Any = _LoopSentinel()


class App(Application):

    def __init__(self, **options):
        super().__init__(**options)
        self._runner: Optional[AppRunner] = None
        self._site: Optional[TCPSite] = None
        self._closing_task: Optional[asyncio.Task] = None
        self._ready: Optional[asyncio.Event] = None
        self.server: Optional[Server] = None

    async def __aenter__(self) -> App:
        return self

    async def __aexit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_value: Optional[BaseException],
            traceback: Optional[TracebackType]
    ) -> None:
        ...

    def _make_handler(
            self,
            *,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            access_log_class: Type[AbstractAccessLogger] = AccessLogger,
            **kwargs: Any,
    ) -> Server:

        """
        Creates a custom Server handler for the application.

        This method is called internally to instantiate our custom Server class
        instead of the default aiohttp RequestHandler. It's where we hook in our
        custom request handling logic.
        """
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

        self.server = Server(
            self._handle,  # type: ignore[arg-type]
            request_factory=self._make_request,
            loop=self._loop,
            **kwargs
        )
        self.server.app = self
        return self.server


    def event(self, coro: Callable[..., Any], /) -> Callable[..., Any]:
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('Event handler must be a coroutine function')
        setattr(self, coro.__name__, coro)
        return coro

    async def on_middleware(self, request: BaseRequest): ...

    async def dispatch(self, event: str, /, *args: Any, **kwargs: Any) -> None:
        method = 'on_' + event
        try:
            coro = getattr(self, method)
            if coro is not None and asyncio.iscoroutinefunction(coro):
                _logger.debug('Dispatching event: %s', event)
                wrapped = self._run_event(coro, method, *args, **kwargs)
                self._loop.create_task(wrapped, name=f'pyguard:{method}')
        except AttributeError:
            pass

    async def _run_event(
            self,
            coro: Callable[..., Any],
            event_name: str,
            *args: Any,
            **kwargs: Any
    ) -> None:
        try:
            await coro(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except Exception as error:
            await self.on_error(event_name, error, *args, **kwargs)

    @staticmethod
    async def on_error(
            event_method: str,
            error: Exception,
            /,
            *args: Any,
            **kwargs: Any
    ) -> None:
        _logger.exception(
            'Error in %s: %s, args: %s kwargs: %s',
            event_method, error, args, kwargs
        )

    async def serve(self, host: str, port: int = 8080, **options: Any) -> None:
        self._site = TCPSite(self._runner, host=host, port=port, **options)
        await self._site.start()

    async def setup_runner(self):
        self._runner = AppRunner(self)
        await self._runner.setup()

    async def start(self, host: str, port: int, **options: Any) -> None:
        await self.setup_runner()
        await self.serve(host, port, **options)

    def run(
            self,
            host: str = 'localhost',
            port: int = 8080,
            *,
            log_handler: Optional[logging.Handler] = None,
            log_level: int = logging.INFO,
            root_logger: bool = False,
            **options
    ) -> None:
        if log_handler is None:
            utils.setup_logging(handler=log_handler, level=log_level, root=root_logger)

        async def runner() -> None:
            async with self:
                await self.start(host, port, **options)
                try:
                    await asyncio.Event().wait()
                except KeyboardInterrupt:
                    pass

        try:
            asyncio.run(runner())
        except KeyboardInterrupt:
            return