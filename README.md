# Demografix Python SDK

Run demographic analysis over names — predicted gender, age, and nationality — from one client. The package
covers [genderize.io](https://genderize.io), [agify.io](https://agify.io), and
[nationalize.io](https://nationalize.io).

## Install

```
pip install demografix
```

The SDK has zero runtime dependencies. It requires Python 3.10 or newer.

## Quickstart

Construct a client, run a list of names through a batch call, read the predictions, and read the quota.

```python
from collections import Counter
from demografix import Demografix

client = Demografix(api_key="YOUR_API_KEY")

names = ["michael", "matthew", "jane", "sofia", "lars"]

batch = client.genderize_batch(names)

split = Counter(r.gender or "unknown" for r in batch.results)
print(split)                      # Counter({'male': 3, 'female': 2})
print(batch.quota.remaining)      # 24987
```

## API keys

An API key is required. Creating one is free and includes 2,500 requests per month. Generate a key in your
dashboard at [genderize.io](https://genderize.io), [agify.io](https://agify.io), or
[nationalize.io](https://nationalize.io). One key works across all three services.

## Usage

### Gender

```python
result = client.genderize("peter")
result.gender          # "male", "female", or None
result.probability     # 1.0
result.count           # 1352696

batch = client.genderize_batch(["michael", "matthew", "jane"])
gender_mix = Counter(r.gender or "unknown" for r in batch.results)
```

### Age

```python
result = client.agify("michael")
result.age             # 57 or None
result.count           # 311558

batch = client.agify_batch(["michael", "matthew", "jane"])
ages = [r.age for r in batch.results if r.age is not None]
average_age = sum(ages) / len(ages)
```

### Nationality

```python
result = client.nationalize("nguyen")
result.country[0].country_id      # "VN"
result.country[0].probability     # 0.891132

batch = client.nationalize_batch(["nguyen", "schmidt", "rossi"])
top_countries = Counter(
    r.country[0].country_id for r in batch.results if r.country
)
```

Each batch accepts at most 10 names. A batch of more than 10 raises `ValidationError` before any request
goes out.

## country_id

`genderize` and `agify` accept an optional `country_id` (ISO 3166-1 alpha-2) to scope the prediction to one
country. Input is case-insensitive; the response echoes it uppercase. `nationalize` has no such parameter.

```python
result = client.genderize("kim", country_id="us")
result.country_id      # "US"

batch = client.agify_batch(["michael", "matthew"], country_id="us")
```

## Quota

Every result and every raised error carries a `quota` read from the response headers. Quota is never cached
on the client; read it from the returned value.

| Field | Meaning |
|---|---|
| `limit` | names allowed in the current window |
| `remaining` | names left in the current window |
| `reset` | seconds until the window resets |

```python
batch = client.genderize_batch(["michael", "matthew"])
batch.quota.remaining
```

## Errors

Non-2xx responses raise a typed exception. Transport failures raise `TransportError`. Every exception
subclasses `DemografixError` and carries `status`, `message`, and `quota` (when the response included
headers).

| Exception | Status | Cause |
|---|---|---|
| `AuthError` | 401 | invalid or missing API key |
| `SubscriptionError` | 402 | expired freebie or inactive subscription |
| `ValidationError` | 422 | bad parameter, or a batch over 10 names (raised client-side) |
| `RateLimitError` | 429 | window exhausted; `quota` is always populated |
| `DemografixError` | other non-2xx | base class for the hierarchy |
| `TransportError` | none | network error, timeout, or non-JSON body |

A `RateLimitError` carries `quota`, so `reset` tells you how long to wait before retrying.

```python
import time
from demografix import Demografix, RateLimitError

client = Demografix(api_key="YOUR_API_KEY")
names = ["michael", "matthew", "jane"]

while True:
    try:
        batch = client.genderize_batch(names)
        break
    except RateLimitError as exc:
        time.sleep(exc.quota.reset)
```

## Methods

| Method | Returns | country_id |
|---|---|---|
| `genderize(name, country_id=None)` | `GenderizeResult` | yes |
| `genderize_batch(names, country_id=None)` | `Batch` of `GenderizePrediction` | yes |
| `agify(name, country_id=None)` | `AgifyResult` | yes |
| `agify_batch(names, country_id=None)` | `Batch` of `AgifyPrediction` | yes |
| `nationalize(name)` | `NationalizeResult` | no |
| `nationalize_batch(names)` | `Batch` of `NationalizePrediction` | no |

A `*Result` exposes the prediction fields directly plus a `quota`. A `Batch` exposes `results` plus one
`quota` for the whole response.

## Reference

Full API reference: [genderize.io/documentation/api](https://genderize.io/documentation/api).
