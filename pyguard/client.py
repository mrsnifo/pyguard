"""
The MIT License (MIT)

Copyright (c) 2026-present mrsnifo

Permission is hereby granted, free of charge, to any person obtaining a
copy of this software and associated documentation files (the "Software"),
to deal in the Software without restriction, including without limitation
the rights to use, copy, modify, merge, publish, distribute, sublicense,
and/or sell copies of the Software, and to permit persons to whom the
Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS
OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NON-INFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING
FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER
DEALINGS IN THE SOFTWARE.
"""

from __future__ import annotations

from aiohttp.web import Application, AppRunner, TCPSite
from typing import Optional, Type, Any, Callable
from aiohttp.abc import AbstractAccessLogger
from aiohttp.web_log import AccessLogger
from types import TracebackType
from .proxy import ClientProxy
from .http import HTTPClient
from .server import Server
from . import errors
from . import utils
import asyncio
import aiohttp
import logging

_logger = logging.getLogger(__name__)

__all__ = ('Client', )


class _LoopSentinel:
    """
    Sentinel used for the default loop before initialization.

    Raises AttributeError when any attribute is accessed before the event
    loop is properly initialized.
    """
    __slots__ = ()

    def __getattr__(self, attr: str) -> None:
        raise AttributeError(
            "Cannot access 'loop' before the app is fully initialized. "
            "Run inside an asynchronous context."
        )


_loop: Any = _LoopSentinel()


class _App(Application):
    """
    Custom aiohttp Application subclass that integrates PyGuard Server.

    Parameters
    ----------
    dispatch: Callable[..., Any]
        The event dispatch function to handle incoming events.
    proxy: ClientProxy
        The client proxy instance for handling proxied requests.
    **kwargs
        Additional keyword arguments passed to the parent Application.

    Attributes
    ----------
    server: Server
        The PyGuard server instance handling requests.
    """

    __slots__ = ('server',)

    def __init__(self,
                 dispatch: Callable[..., Any],
                 proxy: ClientProxy,
                 **kwargs
                 ) -> None:
        super().__init__(**kwargs)
        self._dispatch: Callable[..., Any] = dispatch
        self._proxy: ClientProxy = proxy

    def _make_handler(
            self,
            *,
            loop: Optional[asyncio.AbstractEventLoop] = None,
            access_log_class: Type[AbstractAccessLogger] = AccessLogger,
            **kwargs: Any,
    ) -> Server:
        """
        Create a custom Server instance as the request handler.

        Overrides default aiohttp handler creation to hook in PyGuard's
        request handling and event dispatching.

        Parameters
        ----------
        loop: Optional[asyncio.AbstractEventLoop]
            The event loop to use. If None, uses the current loop.
        access_log_class: Type[AbstractAccessLogger], default=AccessLogger
            The access logger class to use for logging requests.
        **kwargs
            Additional keyword arguments passed to the Server constructor.

        Returns
        -------
        Server
            The configured Server instance.

        Raises
        ------
        TypeError
            If access_log_class is not a subclass of AbstractAccessLogger.
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
            dispatch=self._dispatch,
            proxy=self._proxy,
            handler=self._handle,  # type: ignore[arg-type]
            request_factory=self._make_request,
            **kwargs
        )
        return self.server


class Client:
    """
    PyGuard HTTP proxy server with event-driven request/response interception.

    This client provides an asynchronous HTTP proxy server that allows you to
    intercept, inspect, modify, or forward HTTP requests and responses through
    event handlers. Perfect for building HTTP proxies, request interceptors,
    API gateways, and testing tools.

    Parameters
    ----------
    connector: Optional[aiohttp.BaseConnector]
        Custom aiohttp connector for HTTP connections.
    proxy: Optional[str]
        Proxy URL for outgoing HTTP requests (e.g., 'http://proxy:8080').
    proxy_auth: Optional[aiohttp.BasicAuth]
        Authentication credentials for the proxy.
    http_trace: Optional[aiohttp.TraceConfig]
        Trace configuration for debugging HTTP requests.
    app_logger: Optional[logging.Logger]
        Custom logger for the application.
    app_client_max_size: int, default=1048576
        Maximum size in bytes for client request payloads (default 1MB).
    """

    def __init__(self, **options):
        connector: Optional[aiohttp.BaseConnector] = options.get('connector', None)
        proxy: Optional[str] = options.pop('proxy', None)
        proxy_auth: Optional[aiohttp.BasicAuth] = options.pop('proxy_auth', None)
        http_trace: Optional[aiohttp.TraceConfig] = options.pop('http_trace', None)

        self.loop: asyncio.AbstractEventLoop = _loop

        self.http: HTTPClient = HTTPClient(
            connector,
            proxy=proxy,
            proxy_auth=proxy_auth,
            http_trace=http_trace,
        )

        self.proxy: ClientProxy = ClientProxy(http=self.http)

        app_logger: Optional[logging.Logger] = options.pop('app_logger', None)
        app_client_max_size: int = options.pop('app_client_max_size', 1024**2)
        self.app: _App = _App(self.dispatch, self.proxy, logger=app_logger, client_max_size=app_client_max_size)

        self._runner: Optional[AppRunner] = None
        self._site: Optional[TCPSite] = None
        self._closing_task: Optional[asyncio.Task] = None
        self._ready: asyncio.Event = asyncio.Event()
        self._shutdown: asyncio.Event = asyncio.Event()
        self.server: Optional[Server] = None

    async def __aenter__(self) -> Client:
        """
        Async context manager entry.

        Returns
        -------
        Client
            The client instance.
        """
        return self

    async def __aexit__(
            self,
            exc_type: Optional[Type[BaseException]],
            exc_value: Optional[BaseException],
            traceback: Optional[TracebackType]
    ) -> None:
        """
        Async context manager exit with cleanup.

        Parameters
        ----------
        exc_type: Optional[Type[BaseException]]
            The exception type if an error occurred.
        exc_value: Optional[BaseException]
            The exception instance if an error occurred.
        traceback: Optional[TracebackType]
            The traceback if an error occurred.
        """
        if self._closing_task:
            await self._closing_task
        else:
            await self.close()

    def _async_setup(self) -> None:
        """
        Set up the event loop and async components.

        This method initializes the event loop reference and creates
        the ready and shutdown events for synchronization.
        """
        loop = asyncio.get_running_loop()
        self.loop = loop
        self.proxy.loop = loop
        self._ready = asyncio.Event()
        self._shutdown = asyncio.Event()

    def event(self, coro: Callable[..., Any], /) -> Callable[..., Any]:
        """
        Decorator to register an event handler coroutine.

        Parameters
        ----------
        coro: Callable[..., Any]
            The coroutine function to register as an event handler.
            Must be prefixed with 'on_' (e.g., 'on_request').

        Returns
        -------
        Callable[..., Any]
            The registered coroutine function.

        Raises
        ------
        TypeError
            If the provided function is not a coroutine function.
        """
        if not asyncio.iscoroutinefunction(coro):
            raise TypeError('Event handler must be a coroutine function')
        setattr(self, coro.__name__, coro)
        return coro

    def clear(self) -> None:
        """
        Clear internal references and reset state.

        This method releases resources and resets the client to its
        initial state, allowing for re-initialization if needed.
        """
        self.http.clear()
        self._site = None
        self._runner = None
        self._ready = asyncio.Event()
        self._shutdown = asyncio.Event()
        self.server = None
        self.loop = _loop
        self._closing_task = None

    async def close(self) -> None:
        """
        Gracefully close the application, HTTP client, and server.

        This method ensures all resources are properly cleaned up,
        including stopping the server, cleaning up the runner, and
        closing HTTP connections.
        """
        if self._closing_task:
            return await self._closing_task

        async def _close() -> None:
            self._shutdown.set()

            if self._site is not None:
                await self._site.stop()

            if self._runner is not None:
                await self._runner.cleanup()

            await self.http.close()
        self._closing_task = asyncio.create_task(_close())

        return await self._closing_task

    async def dispatch(self, event: str, /, *args: Any, **kwargs: Any) -> None:
        """
        Dispatch an event to the corresponding event handler coroutine.

        Parameters
        ----------
        event: str
            Event name without the 'on_' prefix (e.g., 'request', 'forward').
        *args: Any
            Positional arguments to pass to the handler.
        **kwargs: Any
            Keyword arguments to pass to the handler.
        """
        method = 'on_' + event
        try:
            coro = getattr(self, method)
            if coro is not None and asyncio.iscoroutinefunction(coro):
                _logger.debug("Dispatching event: %s", event)
                wrapped_coro = self._run_event(coro, method, *args, **kwargs)

                current_async_task = asyncio.current_task()
                if current_async_task is not None:
                    current_async_task.set_name(f"pyguard: {method}")
                    await wrapped_coro
                else:
                    self.loop.create_task(wrapped_coro, name=f"pyguard: {method}")
        except AttributeError:
            pass

    async def _run_event(
            self,
            coro: Callable[..., Any],
            event_name: str,
            *args: Any,
            **kwargs: Any
    ) -> None:
        """
        Internal wrapper to run an event handler and catch exceptions.

        Parameters
        ----------
        coro: Callable[..., Any]
            The coroutine function to execute.
        event_name: str
            The name of the event being handled.
        *args: Any
            Positional arguments for the coroutine.
        **kwargs: Any
            Keyword arguments for the coroutine.
        """
        try:
            await coro(*args, **kwargs)
        except asyncio.CancelledError:
            pass
        except (errors.RequestAborted, errors.RequestForward):
            raise
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
        """
        Default error handler for event processing errors.

        Parameters
        ----------
        event_method: str
            The name of the event method that raised the error.
        error: Exception
            The exception that was raised.
        *args: Any
            Positional arguments that were passed to the event handler.
        **kwargs: Any
            Keyword arguments that were passed to the event handler.
        """
        _logger.exception(
            'Error in %s: %s, args: %s kwargs: %s',
            event_method, error, args, kwargs
        )

    @property
    def is_ready(self) -> bool:
        """
        Returns True if the server is fully running and ready to accept requests.
        """
        return self._ready is not None and self._ready.is_set()

    async def wait_for_ready(self) -> None:
        """
        Wait until the server is ready.

        This is useful for other tasks that need to ensure the server is fully
        operational before sending requests or dispatching dependent events.
        """
        if self._ready is None:
            self._async_setup()
        await self._ready.wait()

    async def serve(self, host: str, port: int, **options: Any) -> None:
        """
        Start serving HTTP requests on the specified host and port.

        Parameters
        ----------
        host: str
            The hostname or IP address to bind to.
        port: int
            The port number to listen on.
        **options
            Additional options passed to TCPSite.
        """
        self._site = TCPSite(self._runner, host=host, port=port, **options)
        await self._site.start()
        await self.dispatch("ready")
        if self._ready:
            self._ready.set()

    async def setup_runner(self):
        """
        Initialize the application runner and event loop.

        This method sets up the event loop if not already initialized
        and creates the AppRunner for the application.
        """
        if self.loop is _loop:
            self._async_setup()
        self._runner = AppRunner(self.app)
        await self._runner.setup()

    async def start(self, host: str, port: int, **options: Any) -> None:
        """
        Set up and start the server in one call.

        Parameters
        ----------
        host: str
            The hostname or IP address to bind to.
        port: int
            The port number to listen on.
        **options
            Additional options passed to the serve method.
        """
        await self.setup_runner()
        await self.serve(host, port, **options)

    def run(
            self,
            host: str = 'localhost',
            port: int = 8080,
            *,
            log_handler: Optional[logging.Handler] = None,
            log_level: int = logging.INFO,
            root_logger: bool = True,
            **options
    ) -> None:
        """
        Run the client application with blocking behavior.

        This is the main entry point for running the client. It sets up
        logging, starts the server, and blocks until interrupted.

        Parameters
        ----------
        host: str
            The hostname or IP address to bind to.
        port: int
            The port number to listen on.
        log_handler: Optional[logging.Handler]
            Custom logging handler. If None, uses default setup.
        log_level: int
            The logging level to use.
        root_logger: bool
            Whether to configure the root logger.
        **options
            Additional options passed to the start method.
        """
        if log_handler is None:
            utils.setup_logging(handler=log_handler, level=log_level, root=root_logger)

        async def runner() -> None:
            async with self:
                await self.start(host, port, **options)
                _logger.debug(f"Server running on {host}:{port}")
                try:
                    await self._shutdown.wait()
                except KeyboardInterrupt:
                    _logger.debug("Received shutdown signal")

        try:
            asyncio.run(runner())
        except KeyboardInterrupt:
            return
