"""Data models for the Demografix SDK.

Predictions hold the fields returned by each service. ``*Result`` types add the
:class:`Quota` for a single call; :class:`Batch` carries one quota for the whole
response.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Generic, Optional, TypeVar


@dataclass(frozen=True, slots=True)
class Quota:
    """Rate-limit state parsed from the response headers.

    Attributes:
        limit: Names allowed in the current window.
        remaining: Names left in the current window.
        reset: Seconds until the window resets.
    """

    limit: int
    remaining: int
    reset: int


@dataclass(slots=True)
class GenderizePrediction:
    """A single genderize prediction.

    ``gender`` is ``"male"``, ``"female"``, or ``None``. ``country_id`` is set
    only when the request sent one.
    """

    name: str
    gender: Optional[str]
    probability: float
    count: int
    country_id: Optional[str] = None


@dataclass(slots=True)
class AgifyPrediction:
    """A single agify prediction.

    ``age`` is an integer or ``None``. ``country_id`` is set only when the
    request sent one.
    """

    name: str
    age: Optional[int]
    count: int
    country_id: Optional[str] = None


@dataclass(slots=True)
class NationalizeCountry:
    """One candidate country for a nationalize prediction."""

    country_id: str
    probability: float


@dataclass(slots=True)
class NationalizePrediction:
    """A single nationalize prediction.

    ``country`` holds up to five candidates in descending probability, or an
    empty list when there is no match.
    """

    name: str
    country: list[NationalizeCountry]
    count: int


@dataclass(slots=True)
class GenderizeResult(GenderizePrediction):
    """A genderize prediction plus the quota for the call."""

    quota: Quota = field(kw_only=True)


@dataclass(slots=True)
class AgifyResult(AgifyPrediction):
    """An agify prediction plus the quota for the call."""

    quota: Quota = field(kw_only=True)


@dataclass(slots=True)
class NationalizeResult(NationalizePrediction):
    """A nationalize prediction plus the quota for the call."""

    quota: Quota = field(kw_only=True)


T = TypeVar("T")


@dataclass(slots=True)
class Batch(Generic[T]):
    """A batch response: per-name predictions plus one quota."""

    results: list[T] = field(default_factory=list)
    quota: Quota = field(kw_only=True)
