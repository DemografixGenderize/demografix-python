"""Demografix Python SDK.

Synchronous and asynchronous clients for genderize.io, agify.io, and
nationalize.io. Call a method, then read the prediction fields and ``quota``.
"""

from .async_client import AsyncDemografix
from .client import Demografix, __version__
from .errors import (
    AuthError,
    DemografixError,
    RateLimitError,
    SubscriptionError,
    TransportError,
    ValidationError,
)
from .models import (
    AgifyPrediction,
    AgifyResult,
    Batch,
    GenderizePrediction,
    GenderizeResult,
    NationalizeCountry,
    NationalizePrediction,
    NationalizeResult,
    Quota,
)

__all__ = [
    "__version__",
    "Demografix",
    "AsyncDemografix",
    "Quota",
    "GenderizePrediction",
    "GenderizeResult",
    "AgifyPrediction",
    "AgifyResult",
    "NationalizeCountry",
    "NationalizePrediction",
    "NationalizeResult",
    "Batch",
    "DemografixError",
    "AuthError",
    "SubscriptionError",
    "ValidationError",
    "RateLimitError",
    "TransportError",
]
