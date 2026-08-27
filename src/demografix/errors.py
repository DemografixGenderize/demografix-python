"""Typed exceptions for the Demografix SDK.

Every error subclasses :class:`DemografixError`. Non-2xx HTTP responses map to a
subclass by status code; transport failures raise :class:`TransportError`.
"""

from __future__ import annotations

from typing import Optional

from .models import Quota


class DemografixError(Exception):
    """Base class for every Demografix error.

    Attributes:
        status: HTTP status code, or ``None`` for transport failures.
        message: The error string from the response body.
        quota: Quota parsed from the rate-limit headers, when present.
    """

    def __init__(
        self,
        message: str,
        status: Optional[int] = None,
        quota: Optional[Quota] = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.message = message
        self.quota = quota


class AuthError(DemografixError):
    """Raised on HTTP 401 (invalid or missing API key)."""


class SubscriptionError(DemografixError):
    """Raised on HTTP 402 (expired freebie or inactive subscription)."""


class ValidationError(DemografixError):
    """Raised on HTTP 422, and client-side when a batch exceeds 100 names."""


class RateLimitError(DemografixError):
    """Raised on HTTP 429. ``quota`` is always populated; ``reset`` is the wait."""


class TransportError(DemografixError):
    """Raised on network failure, timeout, or a non-JSON body.

    ``status`` and ``quota`` may be ``None``.
    """
