from typing import Optional, Callable, Tuple
from aiohttp import web_protocol, web
from aiohttp.web import BaseRequest, StreamResponse
from .http import Request, Response, RequestAborted

class RequestHandler(web_protocol.RequestHandler):

    async def _handle_request(
        self,
        request: BaseRequest,
        start_time: Optional[float],
        _: Callable,
    ) -> Tuple[StreamResponse, bool]:
        self._request_in_progress = True
        try:
            try:
                request.__call__ = Request
                await self._manager.dispatch('request', request)  # type: ignore
                forward = await self._manager.proxy.forward(request) # type: ignore
                forward.__class__ = Response
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
