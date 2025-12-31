from __future__ import annotations

from typing import Any, Callable, Optional, Type, List
from aiohttp import web
from types import TracebackType
from .middleware import Middleware
from .state import ConnectionState
from .proxy import Proxy
import logging
from . import utils
import asyncio

__all__ = ('App',)

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


class App:
    """Main application class."""

    def __init__(self):
        self.loop: asyncio.AbstractEventLoop = _loop
        self._app: Optional[web.Application] = None
        self._runner: Optional[web.AppRunner] = None
        self._site: Optional[web.TCPSite] = None
        self._closing_task: Optional[asyncio.Task] = None
        self._ready: Optional[asyncio.Event] = None
        self.proxy = Proxy(target_url="http://localhost:8030")
        self._state: ConnectionState = ConnectionState(app=self, proxy=self.proxy)
        self._middleware: Middleware = Middleware(state=self._state)

    @property
    def app(self) -> web.Application:
        """Get the underlying aiohttp application."""
        if self._app is None:
            raise RuntimeError("App not initialized. Call setup first.")
        return self._app

    @property
    def router(self) -> web.UrlDispatcher:
        """Get the application router."""
        return self.app.router

    @property
    def state(self) -> ConnectionState:
        """Get the connection state manager."""
        return self._state

    def is_ready(self) -> bool:
        """Check if the app is ready to handle requests."""
        return self._ready is not None and self._ready.is_set()

    async def __aenter__(self) -> App:
        self._async_setup()
        return self

    async def __aexit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_value: Optional[BaseException],
            traceback: Optional[TracebackType]
    ) -> None:
        await self.close()

    def _async_setup(self) -> None:
        """Initialize async components."""
        loop = asyncio.get_running_loop()
        self.loop = loop
        self._ready = asyncio.Event()

    def event(self, coro: Callable[..., Any], /) -> Callable[..., Any]:
        """Register an event handler.

        Usage:
            @app.event
            async def on_request_start(request):
                print(f"Request: {request.path}")
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('Event handler must be a coroutine function')
        setattr(self, coro.__name__, coro)
        _logger.debug("Registered event: %s", coro.__name__)
        return coro

    def dispatch(self, event: str, /, *args: Any, **kwargs: Any) -> None:
        """Dispatch an event to registered handlers."""
        method = 'on_' + event
        try:
            coro = getattr(self, method)
            if coro is not None and asyncio.iscoroutinefunction(coro):
                _logger.debug('Dispatching event: %s', event)
                wrapped = self._run_event(coro, method, *args, **kwargs)
                self.loop.create_task(wrapped, name=f'pyguard:{method}')
        except AttributeError:
            pass

    async def _run_event(
            self,
            coro: Callable[..., Any],
            event_name: str,
            *args: Any,
            **kwargs: Any
    ) -> None:
        """Run an event handler with error handling."""
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
        """Default error handler for events."""
        _logger.exception(
            'Error in %s: %s, args: %s kwargs: %s',
            event_method, error, args, kwargs
        )

    async def setup_hook(self) -> None:
        """Override this to perform setup operations before the app starts."""
        pass

    async def build(self, **options: Any) -> None:
        """Build the aiohttp application."""
        self._app = web.Application(
            middlewares=[*self._middleware],
            **options
        )
        await self.setup_hook()
        self._ready.set()

    async def serve(self, host: str, port: int = 8080, **options: Any) -> None:
        """Start serving the application."""
        self._runner = web.AppRunner(self._app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, host=host, port=port, **options)
        await self._site.start()
        _logger.info(f'Server started at {host}:{port}')
        self.dispatch('serve', host, port)

    async def start(self, host: str = 'localhost', port: int = 8080, **options: Any) -> None:
        """Build and start the application."""
        await self.build()
        await self.serve(host, port, **options)

    async def close(self) -> None:
        """Gracefully close the application."""
        if self._closing_task:
            return await self._closing_task

        async def _close():
            if self._site:
                await self._site.stop()

            if self._runner:
                await self._runner.cleanup()

            if self._ready:
                self._ready.clear()

            self.loop = _loop

        self._closing_task = asyncio.create_task(_close())
        return await self._closing_task

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
        """Run the application (blocking call)."""
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