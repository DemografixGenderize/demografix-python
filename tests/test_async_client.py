"""Unit tests for the native asynchronous Demografix client."""

import asyncio
import json

import httpx
import pytest

from demografix import (
    AsyncDemografix,
    AuthError,
    RateLimitError,
    SubscriptionError,
    TransportError,
    ValidationError,
)
from demografix.client import USER_AGENT

HEADERS = {
    "x-rate-limit-limit": "25000",
    "x-rate-limit-remaining": "24987",
    "x-rate-limit-reset": "1314000",
}


class _Recorder:
    def __init__(self, status, body, headers=None):
        self.status = status
        self.body = body if isinstance(body, bytes) else json.dumps(body).encode()
        self.headers = headers if headers is not None else dict(HEADERS)
        self.urls = []
        self.requests = []


@pytest.fixture
def patch(monkeypatch):
    """Stub ``httpx.AsyncClient.get`` and capture each outgoing request."""

    def install(status, body, headers=None):
        recorder = _Recorder(status, body, headers)

        async def fake_get(client, url):
            request = httpx.Request("GET", url, headers=client.headers)
            recorder.requests.append(request)
            recorder.urls.append(str(request.url))
            return httpx.Response(
                status,
                headers=recorder.headers,
                content=recorder.body,
                request=request,
            )

        monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)
        return recorder

    return install


@pytest.mark.asyncio
async def test_genderize_single_uses_native_async_transport(patch):
    rec = patch(
        200,
        {"count": 1352696, "name": "peter", "gender": "male", "probability": 1.0},
    )

    async with AsyncDemografix("test-key") as client:
        result = await client.genderize("peter")

    assert result.name == "peter"
    assert result.gender == "male"
    assert result.quota.remaining == 24987
    assert "name=peter" in rec.urls[0]
    assert "apikey=test-key" in rec.urls[0]
    assert rec.requests[0].headers["User-Agent"] == USER_AGENT


@pytest.mark.asyncio
async def test_agify_single(patch):
    patch(200, {"count": 311558, "name": "michael", "age": 57})

    async with AsyncDemografix("test-key") as client:
        result = await client.agify("michael")

    assert result.name == "michael"
    assert result.age == 57
    assert result.quota.remaining == 24987


@pytest.mark.asyncio
async def test_nationalize_single(patch):
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

    async with AsyncDemografix("test-key") as client:
        result = await client.nationalize("nguyen")

    assert result.country[0].country_id == "VN"
    assert result.country[0].probability == pytest.approx(0.891132)
    assert result.quota.remaining == 24987


@pytest.mark.asyncio
async def test_batch_preserves_order_and_uses_name_array(patch):
    rec = patch(
        200,
        [
            {"count": 311558, "name": "michael", "age": 57},
            {"count": 55682, "name": "matthew", "age": 48},
        ],
    )

    async with AsyncDemografix("test-key") as client:
        batch = await client.agify_batch(["michael", "matthew"])

    assert [result.name for result in batch.results] == ["michael", "matthew"]
    assert [result.age for result in batch.results] == [57, 48]
    assert batch.quota.remaining == 24987
    assert rec.urls[0].count("name%5B%5D=") == 2


@pytest.mark.asyncio
async def test_one_name_batch_still_uses_name_array(patch):
    rec = patch(
        200,
        [{"count": 1352696, "name": "peter", "gender": "male", "probability": 1.0}],
    )

    async with AsyncDemografix("test-key") as client:
        batch = await client.genderize_batch(["peter"])

    assert [result.name for result in batch.results] == ["peter"]
    assert "name%5B%5D=peter" in rec.urls[0]
    assert "name=peter" not in rec.urls[0]


@pytest.mark.asyncio
async def test_null_prediction_is_a_normal_result(patch):
    patch(200, {"name": "xÿz", "country": [], "count": 0})

    async with AsyncDemografix("test-key") as client:
        result = await client.nationalize("xÿz")

    assert result.country == []
    assert result.count == 0


@pytest.mark.asyncio
async def test_country_id_round_trips(patch):
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

    async with AsyncDemografix("test-key") as client:
        result = await client.genderize("kim", country_id="us")

    assert "country_id=us" in rec.urls[0]
    assert result.country_id == "US"


@pytest.mark.asyncio
async def test_batch_limit_is_checked_before_http(monkeypatch):
    async def boom(*args, **kwargs):
        raise AssertionError("no HTTP call must be made")

    monkeypatch.setattr(httpx.AsyncClient, "get", boom)
    names = [f"n{i}" for i in range(101)]

    async with AsyncDemografix("test-key") as client:
        with pytest.raises(ValidationError) as exc:
            await client.genderize_batch(names)

    assert exc.value.status == 422


@pytest.mark.asyncio
async def test_exactly_100_names_are_allowed(patch):
    names = [f"n{i}" for i in range(100)]
    rec = patch(
        200,
        [{"name": name, "age": i, "count": 1} for i, name in enumerate(names)],
    )

    async with AsyncDemografix("test-key") as client:
        batch = await client.agify_batch(names)

    assert len(batch.results) == 100
    assert rec.urls[0].count("name%5B%5D=") == 100


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("status", "message", "error_type"),
    [
        (401, "Invalid API key", AuthError),
        (402, "Subscription is not active", SubscriptionError),
        (422, "Missing 'name' parameter", ValidationError),
        (429, "Request limit reached", RateLimitError),
    ],
)
async def test_error_status_mapping(patch, status, message, error_type):
    patch(status, {"error": message})

    async with AsyncDemografix("test-key") as client:
        with pytest.raises(error_type) as exc:
            await client.genderize("peter")

    assert exc.value.status == status
    assert exc.value.message == message
    assert exc.value.quota.remaining == 24987


@pytest.mark.asyncio
async def test_network_failure_maps_to_transport_error(monkeypatch):
    async def fail(*args, **kwargs):
        request = httpx.Request("GET", "https://api.genderize.io/")
        raise httpx.ConnectError("network down", request=request)

    monkeypatch.setattr(httpx.AsyncClient, "get", fail)

    async with AsyncDemografix("test-key") as client:
        with pytest.raises(TransportError) as exc:
            await client.genderize("peter")

    assert "network down" in exc.value.message


@pytest.mark.asyncio
async def test_task_cancellation_propagates(monkeypatch):
    started = asyncio.Event()

    async def wait_forever(*args, **kwargs):
        started.set()
        await asyncio.Event().wait()

    monkeypatch.setattr(httpx.AsyncClient, "get", wait_forever)

    async with AsyncDemografix("test-key") as client:
        task = asyncio.create_task(client.genderize("peter"))
        await started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task


@pytest.mark.parametrize("bad_key", ["", "   "])
def test_missing_api_key_raises_before_async_client_is_created(monkeypatch, bad_key):
    def boom(*args, **kwargs):
        raise AssertionError("no HTTP client must be created")

    monkeypatch.setattr(httpx, "AsyncClient", boom)

    with pytest.raises(ValidationError) as exc:
        AsyncDemografix(bad_key)

    assert "api_key is required" in str(exc.value)


@pytest.mark.asyncio
async def test_async_context_manager_closes_connection_pool():
    client = AsyncDemografix("test-key")

    async with client:
        assert not client._http.is_closed

    assert client._http.is_closed
