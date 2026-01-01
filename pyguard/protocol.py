from typing import Optional, Callable, Awaitable, Tuple
from aiohttp.web_exceptions import HTTPException
from aiohttp import web_protocol
import warnings
import asyncio


class RequestHandler(web_protocol.RequestHandler):

    async def _handle_request(
            self,
            request: web_protocol.BaseRequest,
            start_time: Optional[float],
            request_handler: Callable[[web_protocol.BaseRequest], Awaitable[web_protocol.StreamResponse]]
    ) -> Tuple[web_protocol.StreamResponse, bool]:

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
