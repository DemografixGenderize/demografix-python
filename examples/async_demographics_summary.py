"""Summarize names concurrently with the asynchronous Demografix client.

Usage:
    DEMOGRAFIX_API_KEY=your_key python examples/async_demographics_summary.py
"""

import asyncio
import os
from collections import Counter

from demografix import AsyncDemografix

NAMES = [
    "michael",
    "matthew",
    "jane",
    "nguyen",
    "kim",
    "sofia",
    "lars",
    "amara",
]


async def main():
    api_key = os.environ.get("DEMOGRAFIX_API_KEY")
    if not api_key:
        raise SystemExit("Set DEMOGRAFIX_API_KEY to run this example.")

    async with AsyncDemografix(api_key=api_key) as client:
        genders, ages, nationalities = await asyncio.gather(
            client.genderize_batch(NAMES),
            client.agify_batch(NAMES),
            client.nationalize_batch(NAMES),
        )

    gender_split = Counter(result.gender or "unknown" for result in genders.results)
    known_ages = [result.age for result in ages.results if result.age is not None]
    country_mix = Counter(
        result.country[0].country_id
        for result in nationalities.results
        if result.country
    )

    print("Names analyzed: %d" % len(NAMES))
    print("Gender split: %s" % dict(gender_split))
    if known_ages:
        print("Average age: %.1f" % (sum(known_ages) / len(known_ages)))
    print("Nationality mix: %s" % dict(country_mix))
    print("Quota remaining: %d" % nationalities.quota.remaining)


if __name__ == "__main__":
    asyncio.run(main())
