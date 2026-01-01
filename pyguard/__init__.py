"""
pyguard

Event driven HTTP proxy client for intercepting and forwarding requests

Copyright (c) 2026-present mrsnifo
License: MIT, see LICENSE for more details.
"""

__title__ = 'pyguard'
__license__ = 'MIT License'
__author__ = 'mrsnifo'
__copyright__ = 'Copyright 2026-present mrsnifo'
__email__ = 'snifo@mail.com'
__url__ = 'https://github.com/mrsnifo/pyguard'

from .http import Request, Response
from .client import *
from .errors import *

from . import (
    utils as utils,
)
