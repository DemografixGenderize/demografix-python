"""Unit tests for the Demografix Python SDK.

Every request is stubbed at the transport layer by monkeypatching
``urllib.request.urlopen``. No network call is made. Fixtures come from
INTERFACE.md section 5.
"""

import json
import urllib.error
import urllib.request

import pytest

from demografix import (
    AuthError,
    Demografix,
    RateLimitError,
    SubscriptionError,
    ValidationError,
)
from demografix.client import USER_AGENT

HEADERS = {
    "x-rate-limit-limit": "25000",
    "x-rate-limit-remaining": "24987",
    "x-rate-limit-reset": "1314000",
}


class _FakeResponse:
    """Stands in for the object urllib.request.urlopen returns on a 2xx."""

    def __init__(self, status, headers, body):
        self.status = status
        self.headers = headers
        self._body = body

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _Recorder:
    """Captures the outgoing request for assertions in tests."""

    def __init__(self, status, body, headers=None):
        self.status = status
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers = headers if headers is not None else dict(HEADERS)
        self.url = None
        self.request = None


@pytest.fixture
def patch(monkeypatch):
    """Return a helper that installs a recorder and yields it back."""

    def install(status, body, headers=None):
        recorder = _Recorder(status, body, headers)

        def fake_urlopen(request, timeout=None):
            recorder.request = request
            recorder.url = request.full_url
            if 200 <= status < 300:
                return _FakeResponse(
                    status, recorder.headers, recorder.body
                )
            err = urllib.error.HTTPError(
                recorder.url, status, "error", recorder.headers, None
            )
            err.read = lambda: recorder.body  # type: ignore[assignment]
            raise err

        monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
        return recorder

    return install


# -- 1. single parse + quota -------------------------------------------------


def test_genderize_single(patch):
    rec = patch(200, {"count": 1352696, "name": "peter", "gender": "male", "probability": 1.0})
    result = Demografix().genderize("peter")
    assert result.name == "peter"
    assert result.gender == "male"
    assert result.probability == 1.0
    assert result.count == 1352696
    assert result.country_id is None
    assert result.quota.limit == 25000
    assert result.quota.remaining == 24987
    assert result.quota.reset == 1314000
    assert "name=peter" in rec.url
    assert rec.request.get_header("User-agent") == USER_AGENT


def test_agify_single(patch):
    patch(200, {"count": 311558, "name": "michael", "age": 57})
    result = Demografix().agify("michael")
    assert result.name == "michael"
    assert result.age == 57
    assert result.count == 311558
    assert result.quota.remaining == 24987


def test_nationalize_single(patch):
    patch(
        200,
        {
            "count": 100783,
            "name": "nguyen",
            "country": [
                {"country_id": "VN", "probability": 0.891132},
                {"country_id": "MO", "probability": 0.019031},
            ],
        },
    )
    result = Demografix().nationalize("nguyen")
    assert result.name == "nguyen"
    assert len(result.country) == 2
    assert result.country[0].country_id == "VN"
    assert result.country[0].probability == pytest.approx(0.891132)
    assert result.quota.remaining == 24987


# -- 2. batch order + quota --------------------------------------------------


def test_agify_batch_order(patch):
    rec = patch(
        200,
        [
            {"count": 311558, "name": "michael", "age": 57},
            {"count": 55682, "name": "matthew", "age": 48},
        ],
    )
    batch = Demografix().agify_batch(["michael", "matthew"])
    assert [r.name for r in batch.results] == ["michael", "matthew"]
    assert [r.age for r in batch.results] == [57, 48]
    assert batch.quota.remaining == 24987
    assert rec.url.count("name%5B%5D=") == 2
    assert "name%5B%5D=michael" in rec.url
    assert "name%5B%5D=matthew" in rec.url


# -- 3. null prediction is a normal success ----------------------------------


def test_genderize_null(patch):
    patch(200, {"name": "xÿz", "gender": None, "probability": 0.0, "count": 0})
    result = Demografix().genderize("xÿz")
    assert result.gender is None
    assert result.probability == 0.0
    assert result.count == 0


def test_agify_null(patch):
    patch(200, {"name": "xÿz", "age": None, "count": 0})
    result = Demografix().agify("xÿz")
    assert result.age is None
    assert result.count == 0


def test_nationalize_null(patch):
    patch(200, {"name": "xÿz", "country": [], "count": 0})
    result = Demografix().nationalize("xÿz")
    assert result.country == []
    assert result.count == 0


# -- 4. country_id round-trips ------------------------------------------------


def test_country_id_round_trip(patch):
    rec = patch(
        200,
        {
            "count": 196601,
            "name": "kim",
            "gender": "female",
            "country_id": "US",
            "probability": 0.94,
        },
    )
    result = Demografix().genderize("kim", country_id="us")
    assert "country_id=us" in rec.url
    assert result.country_id == "US"
    assert result.gender == "female"


def test_agify_country_id_round_trip(patch):
    rec = patch(200, {"count": 100, "name": "kim", "age": 40, "country_id": "US"})
    result = Demografix().agify("kim", country_id="US")
    assert "country_id=US" in rec.url
    assert result.country_id == "US"


# -- 5. batch over 10 raises client-side, no HTTP ----------------------------


def test_batch_over_ten_no_http(monkeypatch):
    def boom(*args, **kwargs):
        raise AssertionError("no HTTP call must be made")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    names = ["n%d" % i for i in range(11)]
    with pytest.raises(ValidationError) as exc:
        Demografix().genderize_batch(names)
    assert exc.value.status == 422


# -- 6. error status mapping --------------------------------------------------


def test_401_auth_error(patch):
    patch(401, {"error": "Invalid API key"})
    with pytest.raises(AuthError) as exc:
        Demografix().genderize("peter")
    assert exc.value.status == 401
    assert exc.value.message == "Invalid API key"


def test_402_subscription_error(patch):
    patch(402, {"error": "Subscription is not active"})
    with pytest.raises(SubscriptionError) as exc:
        Demografix().genderize("peter")
    assert exc.value.status == 402
    assert exc.value.message == "Subscription is not active"


def test_422_validation_error(patch):
    patch(422, {"error": "Missing 'name' parameter"})
    with pytest.raises(ValidationError) as exc:
        Demografix().genderize("peter")
    assert exc.value.status == 422
    assert exc.value.message == "Missing 'name' parameter"


def test_429_rate_limit_error_carries_quota(patch):
    patch(429, {"error": "Request limit reached"})
    with pytest.raises(RateLimitError) as exc:
        Demografix().genderize("peter")
    assert exc.value.status == 429
    assert exc.value.message == "Request limit reached"
    assert exc.value.quota is not None
    assert exc.value.quota.remaining == 24987
    assert exc.value.quota.reset == 1314000


# -- header case-insensitivity ------------------------------------------------


def test_headers_parsed_case_insensitively(patch):
    upper = {
        "X-Rate-Limit-Limit": "25000",
        "X-Rate-Limit-Remaining": "24987",
        "X-Rate-Limit-Reset": "1314000",
    }
    patch(200, {"count": 1, "name": "peter", "gender": "male", "probability": 1.0}, headers=upper)
    result = Demografix().genderize("peter")
    assert result.quota.remaining == 24987


# -- apikey only sent when set ------------------------------------------------


def test_apikey_omitted_when_absent(patch):
    rec = patch(200, {"count": 1, "name": "peter", "gender": "male", "probability": 1.0})
    Demografix().genderize("peter")
    assert "apikey" not in rec.url


def test_apikey_sent_when_present(patch):
    rec = patch(200, {"count": 1, "name": "peter", "gender": "male", "probability": 1.0})
    Demografix(api_key="secret").genderize("peter")
    assert "apikey=secret" in rec.url
