"""
Real Tech Buy parser (Shopify-based product page).

Price markup looks like:

    <div class="price price--on-sale">
      <dl>
        <div class="price__regular">
          <dd class="price__last"><span class="price-item price-item--regular">Tk 450</span></dd>
        </div>
        <div class="price__sale">
          <dd class="price__compare" data-compare="49000"><s class="price-item price-item--regular">Tk 490</s></dd>
          <dd class="price__last" data-last="45000"><span class="price-item price-item--sale">Tk 450</span></dd>
        </div>
      </dl>
    </div>

`data-compare` / `data-last` are the price in minor units (value / 100). Whether the
product is actually on sale is signalled by the `price--on-sale` class on the outer
`<div class="price ...">` — NOT by comparing compare/last, since those two values can
differ even when the product isn't on sale (e.g. a stale/unused compare-at price).
When not on sale, Regular Price comes from `.price__regular` text and there's no Sale
Price.

Stock status markup looks like:

    <div class="productView-info-item" data-inventory="" data-stock-level="none">
      <span class="productView-info-name">Availability:</span>
      <span class="productView-info-value">Out Of Stock</span>
    </div>

The `data-inventory` attribute is what marks this as the availability row (as opposed
to the Brand/SKU rows nearby), so we select on that rather than matching the "Availability:"
label text. The value text is normalized to "In Stock" / "Out of Stock".
"""

from bs4 import BeautifulSoup

from app.scraping.base import fetch_html, FetchResult, parse_amount_text


def _parse_amount_attr(value):
    if value is None:
        return None
    try:
        return round(int(value) / 100, 2)
    except (TypeError, ValueError):
        return None


def _parse_stock(soup):
    item = soup.select_one(".productView-info-item[data-inventory]")
    if item is None:
        return None

    value_span = item.select_one(".productView-info-value")
    if value_span is None:
        return None

    text = value_span.get_text(strip=True).lower()
    if "out" in text:
        return "Out of Stock"
    if "in" in text:
        return "In Stock"
    return value_span.get_text(strip=True)


def parse(url):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    stock = _parse_stock(soup)

    price_block = soup.select_one(".productView-price") or soup
    price_container = price_block.select_one(".price")
    on_sale = price_container is not None and "price--on-sale" in price_container.get("class", [])

    regular = None
    sale = None

    if on_sale:
        compare_dd = price_block.select_one(".price__sale dd.price__compare[data-compare]")
        last_dd = price_block.select_one(".price__sale dd.price__last[data-last]")
        if compare_dd is not None and last_dd is not None:
            regular = _parse_amount_attr(compare_dd.get("data-compare"))
            sale = _parse_amount_attr(last_dd.get("data-last"))

    if regular is None:
        regular_span = price_block.select_one(".price__regular .price-item--regular")
        regular = parse_amount_text(regular_span.get_text() if regular_span else None)
        sale = None

    if regular is None and stock is None:
        raise RuntimeError(f"Could not find Tech Buy price or stock status on {url}")

    return FetchResult(regular=regular, sale=sale, stock=stock)
