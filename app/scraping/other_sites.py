"""
PLACEHOLDER parser for the "Other website" links.

There are ~5 real competitor sites this will eventually dispatch to by domain (via
registry.py), each with its own real selectors. For now this single placeholder
fabricates a plausible price/stock result from the URL so the app can be built and
tested end-to-end. Replace with real per-site parsers once the user shares each
site's HTML structure.
"""

import hashlib

from app.scraping.base import FetchResult


def parse(url):
    h = int(hashlib.md5((url + "other").encode()).hexdigest(), 16)

    if h % 19 == 0:
        raise RuntimeError(f"Simulated Other-site fetch failure for {url}")

    regular = round(20 + (h % 520) + ((h // 500) % 100) / 100, 2)
    has_sale = (h // 11) % 3 != 0
    sale = round(regular * 0.9, 2) if has_sale else None
    stock = "Out of Stock" if (h % 4) == 0 else "In Stock"

    return FetchResult(regular=regular, sale=sale, stock=stock)
