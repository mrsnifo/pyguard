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

from .errors import RequestAborted, RequestForward, RequestNotHandled
from typing import Optional, Callable, Tuple
from .http import Request, Response
from aiohttp import web_protocol
import logging

__all__ = ('RequestHandler',)

_logger = logging.getLogger(__name__)


class RequestHandler(web_protocol.RequestHandler):
    """Custom request handler that wraps aiohttp.web_protocol.RequestHandler"""

    async def _handle_request(
        self,
        request: web_protocol.BaseRequest,
        start_time: Optional[float],
        _: Callable,
    ) -> Tuple[web_protocol.StreamResponse, bool]:
        """
        Handle an incoming HTTP request.

        This method wraps the original request into a PyGuard Request,
        dispatches the 'request' event, and handles any special exceptions:
        RequestAborted, RequestForward, or RequestNotHandled.

        Parameters
        ----------
        request: web_protocol.BaseRequest
            The incoming aiohttp request.
        start_time: Optional[float]
            The time when the request was received (for timing metrics).
        _: Callable
            Placeholder for compatibility with aiohttp internals.

        Returns
        -------
        Tuple[web_protocol.StreamResponse, bool]
            The aiohttp response to send back and a boolean indicating
            if the connection should be reset.

        Raises
        ------
        RequestNotHandled
            Raised if the request neither responded nor forwarded.
        """
        self._request_in_progress = True

        try:
            request.__class__ = Request
            request._start_time = start_time
            _logger.debug("Received HTTP request: %s %s", request.method, request.path_qs)
            await self._manager.dispatch('request', request)  # type: ignore
            raise RequestNotHandled(request, start_time)

        except RequestAborted as exc:
            _logger.debug("Request responded immediately with status: %s", exc.response.status)
            return await self.finish_response(
                request,
                exc.response,
                start_time,
            )

        except RequestForward as exc:
            _logger.debug("Forwarding HTTP request to URL: %s", exc.url)
            forward = await self._manager.proxy.forward(exc.url, exc.request)  # type: ignore
            forward.__class__ = Response
            try:
                await self._manager.dispatch('forward', forward)  # type: ignore
                return await self.finish_response(
                    request,
                    forward,
                    start_time,
                )
            except RequestAborted as exc:
                return await self.finish_response(
                    request,
                    exc.response,
                    start_time,
                )

        finally:
            self._request_in_progress = False
            if self._handler_waiter is not None:
                self._handler_waiter.set_result(None)
