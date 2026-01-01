from __future__ import annotations

import asyncio
from typing import Optional, Type, Any
from aiohttp.abc import AbstractAccessLogger
from aiohttp.web import Application, AppRunner, TCPSite
from aiohttp.web_log import AccessLogger
from types import TracebackType
from .server import Server
import logging
from . import utils


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

        Parameters
        ----------
        loop: Optional[asyncio.AbstractEventLoop]
            Event loop to use for async operations. If None, uses the app's loop.
        access_log_class: Type[AbstractAccessLogger]
            Logger class for access logs. Must inherit from AbstractAccessLogger.
        **kwargs: Any
            Additional arguments passed to the Server constructor.

        Returns
        -------
        Server
            Our custom Server instance that will handle incoming requests.

        Raises
        ------
        TypeError
            If access_log_class doesn't inherit from AbstractAccessLogger.
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

        server = Server(
            self._handle,  # type: ignore[arg-type]
            request_factory=self._make_request,
            loop=self._loop,
            **kwargs,
        )
        return server

    async def serve(self, host: str, port: int = 8080, **options: Any) -> None:
        self._site = TCPSite(self._runner, host=host, port=port, **options)
        await self._site.start()

    async def setup_runner(self):
        self._runner = AppRunner(self)
        await self._runner.setup()

    async def start(self, host: str = 'localhost', port: int = 8080, **options: Any) -> None:
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