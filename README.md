# Demografix Python SDK

Predict gender, age, and nationality from names. One Python client covers all three Demografix
APIs — [genderize.io](https://genderize.io) (gender), [agify.io](https://agify.io) (age), and
[nationalize.io](https://nationalize.io) (nationality) — with single-name lookups and batches of up
to 100 names per request.

[![PyPI](https://img.shields.io/pypi/v/demografix)](https://pypi.org/project/demografix/)
[![CI](https://github.com/DemografixGenderize/demografix-python/actions/workflows/ci.yml/badge.svg)](https://github.com/DemografixGenderize/demografix-python/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/license-MIT-blue)](LICENSE)

## Install

```sh
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

## genderize

Predict gender from names. A single call returns the prediction fields plus a `quota`.

```python
result = client.genderize("peter")
result.gender          # "male", "female", or None
result.probability     # 1.0
result.count           # 1352696
result.quota.remaining # 24987
```

The batch form reduces a list to a gender split.

```python
batch = client.genderize_batch(["michael", "matthew", "jane"])
gender_mix = Counter(r.gender or "unknown" for r in batch.results)
```

`gender` is `None` when no match is found, with `probability` `0.0` and `count` `0`. That is a
successful response, not an error.

## agify

Predict age from names. Aggregate a batch into an age distribution.

```python
result = client.agify("michael")
result.age             # 57 or None
result.count           # 311558

batch = client.agify_batch(["michael", "matthew", "jane"])
ages = [r.age for r in batch.results if r.age is not None]
average_age = sum(ages) / len(ages)
```

`age` is an integer or `None`.

## nationalize

Predict nationality from names. Each prediction carries up to five candidate countries in descending probability.

```python
result = client.nationalize("nguyen")
result.country[0].country_id      # "VN"
result.country[0].probability     # 0.891132

batch = client.nationalize_batch(["nguyen", "schmidt", "rossi"])
top_countries = Counter(
    r.country[0].country_id for r in batch.results if r.country
)
```

`country` is an empty list when no match is found.

## Batch limit

Each batch accepts at most 100 names. A batch of more than 100 raises `ValidationError` before any
request goes out. Chunk a longer list and aggregate across the chunks.

```python
def chunked(items, size=100):
    for i in range(0, len(items), size):
        yield items[i : i + size]

split = Counter()
for chunk in chunked(roster):
    batch = client.genderize_batch(chunk)
    split.update(r.gender or "unknown" for r in batch.results)
```

## country_id

`genderize` and `agify` accept an optional `country_id` (ISO 3166-1 alpha-2) to scope the prediction
to one country. Input is case-insensitive; the response echoes it uppercase on every prediction.
`nationalize` has no such parameter.

```python
result = client.genderize("kim", country_id="us")
result.country_id      # "US"

# Scope a whole list, then aggregate.
batch = client.agify_batch(["kim", "andrea", "jan"], country_id="us")
ages = [r.age for r in batch.results if r.age is not None]
batch.results[0].country_id   # "US", echoed uppercase on each prediction
```

Scoping changes the prediction: `andrea` reads mostly female in the United States and mostly male in
Italy. When the request sends no `country_id`, the field is `None`.

## Quota

Every result and every raised error carries a `quota` read from the response headers. Quota is never
cached on the client; read it from the returned value.

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
| `ValidationError` | 422 | bad parameter, or a batch over 100 names (raised client-side) |
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

A `*Result` exposes the prediction fields directly plus a `quota`. A `Batch` exposes `results` plus
one `quota` for the whole response. `Demografix(api_key, timeout=10.0)` requires `api_key`; the host
URLs and the User-Agent are fixed constants, not options.

## API keys

An API key is required. Creating one is free and includes 2,500 names per month.

Quota counts **names, not requests**. A single-name call costs 1. A batch of 100 names costs 100. The
free tier therefore covers 2,500 names in a month however they are split across calls.

Generate a key in your dashboard at [genderize.io](https://genderize.io),
[agify.io](https://agify.io), or [nationalize.io](https://nationalize.io). One key works across all
three services. Full reference: [genderize.io/documentation/api](https://genderize.io/documentation/api).

## License

MIT. See [LICENSE](LICENSE).
