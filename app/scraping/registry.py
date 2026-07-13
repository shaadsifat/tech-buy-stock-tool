"""
Dispatches a URL to the right parser.

Tech Buy is always the same retailer, so every techbuy_link uses `techbuy.parse`.

The "Other website" links can be one of ~5 known competitor sites. As real per-site
parsers are added (keyed by domain, without "www."), register them in
OTHER_SITE_PARSERS below. Anything not yet registered falls back to the generic
placeholder in other_sites.py.
"""

from urllib.parse import urlparse

from app.scraping import techbuy
from app.scraping import startech
from app.scraping import other_sites

OTHER_SITE_PARSERS = {
    "startech.com.bd": startech.parse,
}


def _domain(url):
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def get_techbuy_parser(url):
    return techbuy.parse


def get_other_parser(url):
    domain = _domain(url)
    return OTHER_SITE_PARSERS.get(domain, other_sites.parse)
