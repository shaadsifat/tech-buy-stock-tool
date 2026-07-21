"""
Dispatches an "Other website" URL to the right parser.

Tech Buy's own price/stock comes from the Shopify catalog sync (get_product_api_call.py),
not scraping — this registry only handles the competitor ("Other") side.

The "Other website" links can be one of ~5 known competitor sites. As real per-site
parsers are added (keyed by domain, without "www."), register them in
OTHER_SITE_PARSERS below. Anything not yet registered falls back to the generic
placeholder in other_sites.py.
"""

from urllib.parse import urlparse

from app.scraping import startech
from app.scraping import other_sites

OTHER_SITE_PARSERS = {
    "startech.com.bd": startech.parse,
}

# Only registered for sites with a variant-aware parser (returns every option
# combination's price/stock, not just one) — used for variant-parent products instead
# of OTHER_SITE_PARSERS. A domain without an entry here falls back to the single-price
# parser applied uniformly to every variant (see runner._fetch_variant_product).
OTHER_SITE_VARIANT_PARSERS = {
    "startech.com.bd": startech.parse_variants,
}

# Human-friendly name per domain, for display purposes (e.g. the Other Websites
# page). Anything not listed here just falls back to showing the raw domain.
SITE_DISPLAY_NAMES = {
    "startech.com.bd": "StarTech",
}


def domain_of(url):
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def get_other_parser(url):
    domain = domain_of(url)
    return OTHER_SITE_PARSERS.get(domain, other_sites.parse)


def get_variant_parser(url):
    """None if this domain has no variant-aware parser registered."""
    return OTHER_SITE_VARIANT_PARSERS.get(domain_of(url))


def get_site_display_name(domain):
    return SITE_DISPLAY_NAMES.get(domain, domain)
