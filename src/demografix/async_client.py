"""The asynchronous Demografix client."""

from __future__ import annotations

import json
import urllib.parse
from typing import Any, Mapping, Optional

import httpx

from .client import (
    AGIFY_HOST,
    DEFAULT_TIMEOUT,
    GENDERIZE_HOST,
    MAX_BATCH,
    NATIONALIZE_HOST,
    USER_AGENT,
    _ERROR_TYPES,
    _parse_agify,
    _parse_genderize,
    _parse_nationalize,
    _parse_quota,
)
from .errors import DemografixError, TransportError, ValidationError
from .models import (
    AgifyResult,
    Batch,
    GenderizeResult,
    NationalizeResult,
    Quota,
)


class AsyncDemografix:
    """Asynchronous client for genderize, agify, and nationalize.

    Methods have the same names, arguments, models, and errors as the
    synchronous :class:`demografix.Demografix` client. Use the client as an
    async context manager or call :meth:`aclose` to close its connection pool.

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
        self._http = httpx.AsyncClient(
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            timeout=timeout,
        )

    async def aclose(self) -> None:
        """Close the client's HTTP connection pool."""
        await self._http.aclose()

    async def __aenter__(self) -> AsyncDemografix:
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    # -- public API: single ------------------------------------------------

    async def genderize(
        self, name: str, country_id: Optional[str] = None
    ) -> GenderizeResult:
        """Predict gender for one name. Optionally scope by ``country_id``."""
        body, quota = await self._get(GENDERIZE_HOST, [name], country_id)
        pred = _parse_genderize(body)
        return GenderizeResult(
            name=pred.name,
            gender=pred.gender,
            probability=pred.probability,
            count=pred.count,
            country_id=pred.country_id,
            quota=quota,
        )

    async def agify(
        self, name: str, country_id: Optional[str] = None
    ) -> AgifyResult:
        """Predict age for one name. Optionally scope by ``country_id``."""
        body, quota = await self._get(AGIFY_HOST, [name], country_id)
        pred = _parse_agify(body)
        return AgifyResult(
            name=pred.name,
            age=pred.age,
            count=pred.count,
            country_id=pred.country_id,
            quota=quota,
        )

    async def nationalize(self, name: str) -> NationalizeResult:
        """Predict nationality for one name."""
        body, quota = await self._get(NATIONALIZE_HOST, [name], None)
        pred = _parse_nationalize(body)
        return NationalizeResult(
            name=pred.name,
            country=pred.country,
            count=pred.count,
            quota=quota,
        )

    # -- public API: batch -------------------------------------------------

    async def genderize_batch(
        self, names: list[str], country_id: Optional[str] = None
    ) -> Batch:
        """Predict gender for up to 100 names. Optionally scope by ``country_id``."""
        self._check_batch(names)
        body, quota = await self._get(GENDERIZE_HOST, names, country_id, batch=True)
        results = [_parse_genderize(item) for item in body]
        return Batch(results=results, quota=quota)

    async def agify_batch(
        self, names: list[str], country_id: Optional[str] = None
    ) -> Batch:
        """Predict age for up to 100 names. Optionally scope by ``country_id``."""
        self._check_batch(names)
        body, quota = await self._get(AGIFY_HOST, names, country_id, batch=True)
        results = [_parse_agify(item) for item in body]
        return Batch(results=results, quota=quota)

    async def nationalize_batch(self, names: list[str]) -> Batch:
        """Predict nationality for up to 100 names."""
        self._check_batch(names)
        body, quota = await self._get(NATIONALIZE_HOST, names, None, batch=True)
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

    async def _get(
        self,
        host: str,
        names: list[str],
        country_id: Optional[str],
        batch: bool = False,
    ) -> tuple[Any, Quota]:
        url = host + "/?" + self._build_query(names, country_id, batch)
        status, headers, raw = await self._request(url)
        quota = _parse_quota(headers)
        return self._decode(status, raw, quota), quota

    def _build_query(
        self, names: list[str], country_id: Optional[str], batch: bool
    ) -> str:
        params: list[tuple[str, str]] = []
        if batch:
            for name in names:
                params.append(("name[]", name))
        else:
            params.append(("name", names[0]))
        if country_id is not None:
            params.append(("country_id", country_id))
        params.append(("apikey", self._api_key))
        return urllib.parse.urlencode(params)

    @staticmethod
    def _decode(status: int, raw: bytes, quota: Quota) -> Any:
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

    async def _request(
        self, url: str
    ) -> tuple[int, Mapping[str, str], bytes]:
        """Dispatch one request through the asynchronous transport seam."""
        try:
            response = await self._http.get(url)
        except httpx.HTTPError as exc:
            raise TransportError(f"Request failed: {exc}") from exc
        return response.status_code, response.headers, response.content
