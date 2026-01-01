import logging
from aiohttp import web
from .proxy import Proxy

_logger = logging.getLogger(__name__)


class ConnectionState:
    def __init__(self, dispatch: Callable[..., Any]):
        ...