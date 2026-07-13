"""
Real StarTech.com.bd parser.

Markup (product-info-table):

    <tr class="product-info-group">
      <td class="product-info-label">Price</td>
      <td class="product-info-data product-price">300৳</td>
    </tr>
    <tr class="product-info-group">
      <td class="product-info-label">Regular Price</td>
      <td class="product-info-data product-regular-price">330৳</td>
    </tr>
    <tr class="product-info-group">
      <td class="product-info-label">Status</td>
      <td class="product-info-data product-status">In Stock</td>
    </tr>

When on sale, the "Price" cell can contain <ins>current</ins><del>old</del> — the <del>
value is unreliable (confirmed by example data: it doesn't even match the separate
"Regular Price" row) and must be ignored completely; only <ins> is used.

- If a "Regular Price" row exists: Regular Price = that row's value, Sale Price = the
  "Price" cell's value (via <ins> if present, else the plain cell text).
- If no "Regular Price" row exists: Regular Price = the "Price" cell's value, no Sale
  Price.
- Some out-of-stock/discontinued products show "To be announced" instead of a number
  (no "Regular Price" row either) — this fails to parse and is treated as a fetch
  problem (raises), same as any other unparseable price.

Status cell values seen so far: "In Stock", "Sold Out" (mapped to "Out of Stock").
"""

from bs4 import BeautifulSoup

from app.scraping.base import fetch_html, FetchResult, parse_amount_text


def _price_cell_text(cell):
    del_tag = cell.select_one("del")
    if del_tag is not None:
        del_tag.extract()  # discard garbage <del> value entirely
    return cell.get_text(strip=True)


def _parse_stock(soup):
    status_cell = soup.select_one(".product-status")
    if status_cell is None:
        return None

    text = status_cell.get_text(strip=True).lower()
    if "in stock" in text:
        return "In Stock"
    if "sold out" in text or "out of stock" in text:
        return "Out of Stock"
    return status_cell.get_text(strip=True)


def parse(url):
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    price_cell = soup.select_one(".product-price")
    regular_row = soup.select_one(".product-regular-price")

    if regular_row is not None:
        regular = parse_amount_text(regular_row.get_text(strip=True))
        sale = parse_amount_text(_price_cell_text(price_cell)) if price_cell is not None else None
    else:
        regular = parse_amount_text(_price_cell_text(price_cell)) if price_cell is not None else None
        sale = None

    if regular is None:
        raise RuntimeError(f"Could not find StarTech regular price on {url}")

    stock = _parse_stock(soup)

    return FetchResult(regular=regular, sale=sale, stock=stock)
