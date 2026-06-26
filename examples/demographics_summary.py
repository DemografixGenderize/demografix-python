"""Summarize the demographic mix of a list of names.

Run a roster through all three services in batches of 10 and print an aggregate
gender split, age distribution, and nationality mix across the whole list.

Usage:
    DEMOGRAFIX_API_KEY=your_key python examples/demographics_summary.py
"""

import os
from collections import Counter

from demografix import Demografix

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


def chunked(items, size):
    for start in range(0, len(items), size):
        yield items[start : start + size]


def main():
    api_key = os.environ.get("DEMOGRAFIX_API_KEY")
    if not api_key:
        raise SystemExit("Set DEMOGRAFIX_API_KEY to run this example.")
    client = Demografix(api_key=api_key)

    genders = Counter()
    ages = []
    countries = Counter()
    remaining = None

    for chunk in chunked(NAMES, 10):
        g = client.genderize_batch(chunk)
        a = client.agify_batch(chunk)
        n = client.nationalize_batch(chunk)
        remaining = n.quota.remaining

        for prediction in g.results:
            genders[prediction.gender or "unknown"] += 1
        for prediction in a.results:
            if prediction.age is not None:
                ages.append(prediction.age)
        for prediction in n.results:
            if prediction.country:
                countries[prediction.country[0].country_id] += 1

    total = len(NAMES)
    print("Names analyzed: %d" % total)

    print("\nGender split:")
    for gender, count in genders.most_common():
        print("  %-8s %d (%.0f%%)" % (gender, count, 100 * count / total))

    if ages:
        print("\nAge distribution:")
        print("  count   %d" % len(ages))
        print("  min     %d" % min(ages))
        print("  median  %d" % sorted(ages)[len(ages) // 2])
        print("  max     %d" % max(ages))

    print("\nTop nationality mix:")
    for country_id, count in countries.most_common(5):
        print("  %-4s %d" % (country_id, count))

    if remaining is not None:
        print("\nQuota remaining: %d" % remaining)


if __name__ == "__main__":
    main()
