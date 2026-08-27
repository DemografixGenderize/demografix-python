"""The Demografix client.

One client covers all three services. The per-service hosts and the User-Agent
are hardcoded constants. Every request passes through :meth:`Demografix._request`,
the single transport seam tests stub.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Mapping, Optional

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

__version__ = "0.2.0"

GENDERIZE_HOST = "https://api.genderize.io"
AGIFY_HOST = "https://api.agify.io"
NATIONALIZE_HOST = "https://api.nationalize.io"
USER_AGENT = "demografix-python/" + __version__

DEFAULT_TIMEOUT = 10.0
MAX_BATCH = 100

_ERROR_TYPES = {
    401: AuthError,
    402: SubscriptionError,
    422: ValidationError,
    429: RateLimitError,
}


class Demografix:
    """Synchronous client for genderize, agify, and nationalize.

    Args:
        api_key: API key, required. The same key works across all three
            services. An empty or blank key raises :class:`ValidationError`.
        timeout: Per-request timeout in seconds. Defaults to 10.
    """

    def __init__(
        self,
        api_key: str,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        if not api_key or not api_key.strip():
            raise ValidationError("api_key is required", status=422)
        self._api_key = api_key
        self._timeout = timeout

    # -- public API: single ------------------------------------------------

    def genderize(
        self, name: str, country_id: Optional[str] = None
    ) -> GenderizeResult:
        """Predict gender for one name. Optionally scope by ``country_id``."""
        body, quota = self._get(GENDERIZE_HOST, [name], country_id)
        pred = _parse_genderize(body)
        return GenderizeResult(
            name=pred.name,
            gender=pred.gender,
            probability=pred.probability,
            count=pred.count,
            country_id=pred.country_id,
            quota=quota,
        )

    def agify(self, name: str, country_id: Optional[str] = None) -> AgifyResult:
        """Predict age for one name. Optionally scope by ``country_id``."""
        body, quota = self._get(AGIFY_HOST, [name], country_id)
        pred = _parse_agify(body)
        return AgifyResult(
            name=pred.name,
            age=pred.age,
            count=pred.count,
            country_id=pred.country_id,
            quota=quota,
        )

    def nationalize(self, name: str) -> NationalizeResult:
        """Predict nationality for one name."""
        body, quota = self._get(NATIONALIZE_HOST, [name], None)
        pred = _parse_nationalize(body)
        return NationalizeResult(
            name=pred.name,
            country=pred.country,
            count=pred.count,
            quota=quota,
        )

    # -- public API: batch -------------------------------------------------

    def genderize_batch(
        self, names: list[str], country_id: Optional[str] = None
    ) -> Batch:
        """Predict gender for up to 100 names. Optionally scope by ``country_id``."""
        self._check_batch(names)
        body, quota = self._get(GENDERIZE_HOST, names, country_id, batch=True)
        results = [_parse_genderize(item) for item in body]
        return Batch(results=results, quota=quota)

    def agify_batch(
        self, names: list[str], country_id: Optional[str] = None
    ) -> Batch:
        """Predict age for up to 100 names. Optionally scope by ``country_id``."""
        self._check_batch(names)
        body, quota = self._get(AGIFY_HOST, names, country_id, batch=True)
        results = [_parse_agify(item) for item in body]
        return Batch(results=results, quota=quota)

    def nationalize_batch(self, names: list[str]) -> Batch:
        """Predict nationality for up to 100 names."""
        self._check_batch(names)
        body, quota = self._get(NATIONALIZE_HOST, names, None, batch=True)
        results = [_parse_nationalize(item) for item in body]
        return Batch(results=results, quota=quota)

    # -- internals ---------------------------------------------------------

    @staticmethod
    def _check_batch(names: list[str]) -> None:
        if len(names) > MAX_BATCH:
            raise ValidationError(
                f"A batch accepts at most {MAX_BATCH} names, got {len(names)}",
                status=422,
            )

    def _get(
        self,
        host: str,
        names: list[str],
        country_id: Optional[str],
        batch: bool = False,
    ) -> tuple[Any, Quota]:
        """Build the URL, dispatch through the seam, decode, and map errors."""
        url = host + "/?" + self._build_query(names, country_id, batch)
        status, headers, raw = self._request(url)
        quota = _parse_quota(headers)
        return self._decode(status, raw, quota), quota

    def _build_query(
        self, names: list[str], country_id: Optional[str], batch: bool
    ) -> str:
        params: list[tuple[str, str]] = []
        if batch:
            # Always name[], even for one name: the API keys its response
            # shape on the parameter form, and a batch call must get a list.
            for name in names:
                params.append(("name[]", name))
        else:
            params.append(("name", names[0]))
        if country_id is not None:
            params.append(("country_id", country_id))
        params.append(("apikey", self._api_key))
        return urllib.parse.urlencode(params)

    def _decode(self, status: int, raw: bytes, quota: Quota) -> Any:
        try:
            body = json.loads(raw.decode("utf-8"))
        except (ValueError, UnicodeDecodeError) as exc:
            raise TransportError(
                f"Non-JSON response body: {exc}",
                status=status,
                quota=quota,
            ) from exc
        if 200 <= status < 300:
            return body
        message = body.get("error", "") if isinstance(body, dict) else ""
        error_type = _ERROR_TYPES.get(status, DemografixError)
        raise error_type(message, status=status, quota=quota)

    def _request(self, url: str) -> tuple[int, Mapping[str, str], bytes]:
        """The single transport seam. Tests stub this or ``urlopen``.

        Returns ``(status, headers, body_bytes)``. HTTP error statuses come back
        as a tuple here, not as raised exceptions; only true transport failures
        raise :class:`TransportError`.
        """
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"User-Agent": USER_AGENT},
        )
        try:
            response = urllib.request.urlopen(request, timeout=self._timeout)
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            return exc.code, exc.headers, raw
        except urllib.error.URLError as exc:
            raise TransportError(f"Request failed: {exc.reason}") from exc
        except (TimeoutError, OSError) as exc:
            raise TransportError(f"Request failed: {exc}") from exc
        with response:
            return response.status, response.headers, response.read()


# -- header and body parsing -------------------------------------------------


def _header(headers: Mapping[str, str], name: str) -> Optional[str]:
    """Read a header case-insensitively across mapping implementations."""
    getter = getattr(headers, "get", None)
    if getter is not None:
        value = getter(name)
        if value is not None:
            return value
    lowered = name.lower()
    for key in headers:
        if key.lower() == lowered:
            return headers[key]
    return None


def _parse_quota(headers: Mapping[str, str]) -> Quota:
    return Quota(
        limit=int(_header(headers, "x-rate-limit-limit") or 0),
        remaining=int(_header(headers, "x-rate-limit-remaining") or 0),
        reset=int(_header(headers, "x-rate-limit-reset") or 0),
    )


def _parse_genderize(item: dict[str, Any]) -> GenderizePrediction:
    return GenderizePrediction(
        name=item["name"],
        gender=item.get("gender"),
        probability=float(item.get("probability", 0.0)),
        count=int(item.get("count", 0)),
        country_id=item.get("country_id"),
    )


def _parse_agify(item: dict[str, Any]) -> AgifyPrediction:
    return AgifyPrediction(
        name=item["name"],
        age=item.get("age"),
        count=int(item.get("count", 0)),
        country_id=item.get("country_id"),
    )


def _parse_nationalize(item: dict[str, Any]) -> NationalizePrediction:
    country = [
        NationalizeCountry(
            country_id=c["country_id"],
            probability=float(c["probability"]),
        )
        for c in item.get("country", [])
    ]
    return NationalizePrediction(
        name=item["name"],
        country=country,
        count=int(item.get("count", 0)),
    )
