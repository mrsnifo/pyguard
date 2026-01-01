import logging
_logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


class Proxy:
    """Reverse proxy supporting HTTP and WebSocket."""

    __slots__ = ('loop', )

    def __init__(self):

        ...