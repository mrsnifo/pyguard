from typing import Optional, Callable, Tuple
from aiohttp import web_protocol, web
from aiohttp.web import BaseRequest, StreamResponse
from .http import CustomRequest, _RespondNow  # import the internal exception

class RequestHandler(web_protocol.RequestHandler):

    async def _handle_request(
        self,
        request: BaseRequest,
        start_time: Optional[float],
        _: Callable,
    ) -> Tuple[StreamResponse, bool]:

        self._request_in_progress = True
        try:
            rq = CustomRequest(request)

            try:
                # Call middleware, which may call rq.respond()
                await self._manager.app.on_middleware(rq)
            except _RespondNow as exc:
                # Middleware requested an immediate response
                return await self.finish_response(
                    request,
                    exc.response,
                    start_time,
                )

            # Default response if no middleware responded
            return await self.finish_response(
                request,
                web.Response(text="OK"),
                start_time,
            )

        finally:
            self._request_in_progress = False
            if self._handler_waiter is not None:
                self._handler_waiter.set_result(None)
