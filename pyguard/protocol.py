from typing import Optional, Callable, Tuple
from aiohttp import web_protocol, web
from aiohttp.web import BaseRequest, StreamResponse
from .http import Request, RequestAborted

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
                await self._manager.dispatch('middleware', Request(request))
            except RequestAborted as exc:
                return await self.finish_response(
                    request,
                    exc.response,
                    start_time,
                )
            return await self.finish_response(
                request,
                web.Response(text="OK"),
                start_time,
            )

        finally:
            self._request_in_progress = False
            if self._handler_waiter is not None:
                self._handler_waiter.set_result(None)
