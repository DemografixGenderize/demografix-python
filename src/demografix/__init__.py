"""Demografix Python SDK.

One client for genderize.io, agify.io, and nationalize.io. Construct
:class:`Demografix`, call a method, read the prediction fields and ``quota``.
"""

from .client import Demografix
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

__version__ = "0.1.0"

__all__ = [
    "Demografix",
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
