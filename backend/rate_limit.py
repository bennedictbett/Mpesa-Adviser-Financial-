"""
Shared rate limiter instance. Lives in its own module (not main.py)
specifically to avoid a circular import between main.py and the
route files that need to reference the limiter via @limiter.limit(...).
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

limiter = Limiter(key_func=get_remote_address)