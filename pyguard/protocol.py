from typing import Optional, Callable, Tuple
from aiohttp import web_protocol
from .http import Request, Response
from .errors import RequestAborted, RequestForward, RequestNotHandled



class RequestHandler(web_protocol.RequestHandler):

    async def _handle_request(
        self,
        request: web_protocol.BaseRequest,
        start_time: Optional[float],
        _: Callable,
    ) -> Tuple[web_protocol.StreamResponse, bool]:
        self._request_in_progress = True
        try:
            try:
                request.__class__ = Request
                await self._manager.dispatch('request', request)  # type: ignore
                raise RequestNotHandled(request, start_time)
            except RequestAborted as exc:
                return await self.finish_response(
                    request,
                    exc.response,
                    start_time,
                )
            except RequestForward as exc:
                forward = await self._manager.proxy.forward(exc.target_url, exc.request)  # type: ignore
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
