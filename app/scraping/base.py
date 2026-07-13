import re

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15


def fetch_html(url):
    """Fetch a page's HTML. Raises on failure (caller is responsible for catching)."""
    response = requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
    response.raise_for_status()
    return response.text


class FetchResult:
    """Normalized result every site parser must return."""

    def __init__(self, regular, sale, stock):
        self.regular = regular  # float or None
        self.sale = sale        # float or None
        self.stock = stock      # "In Stock" / "Out of Stock"


def parse_amount_text(text):
    """Strips currency symbols/commas/whitespace (e.g. 'Tk 1,299', '330৳') to a float."""
    if not text:
        return None
    digits = re.sub(r"[^\d.]", "", text)
    if not digits:
        return None
    try:
        return round(float(digits), 2)
    except ValueError:
        return None
