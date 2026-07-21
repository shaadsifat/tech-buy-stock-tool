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
  (no "Regular Price" row either). When that happens but stock status IS readable,
  we still return it — Regular/Sale Price just stay blank. Only raises (treated as a
  fetch problem) when NEITHER price nor stock could be found at all.

Status cell values seen so far: "In Stock", "Sold Out" (mapped to "Out of Stock").
"""

import itertools
import re

from bs4 import BeautifulSoup

from app.scraping.base import fetch_html, post_form, FetchResult, parse_amount_text

VARIATION_URL = "https://www.startech.com.bd/product/product/variation"


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

    stock = _parse_stock(soup)

    price_cell = soup.select_one(".product-price")
    regular_row = soup.select_one(".product-regular-price")

    if regular_row is not None:
        regular = parse_amount_text(regular_row.get_text(strip=True))
        sale = parse_amount_text(_price_cell_text(price_cell)) if price_cell is not None else None
    else:
        regular = parse_amount_text(_price_cell_text(price_cell)) if price_cell is not None else None
        sale = None

    if regular is None and stock is None:
        raise RuntimeError(f"Could not find StarTech price or stock status on {url}")

    return FetchResult(regular=regular, sale=sale, stock=stock)


def _map_stock(text):
    if not text:
        return None
    text = text.strip().lower()
    if "in stock" in text:
        return "In Stock"
    if "out of stock" in text or "sold out" in text:
        return "Out of Stock"
    return text


def _extract_product_id(soup):
    """The Add to Cart form's hidden product_id input is the same numeric id the
    variation endpoint expects — more reliable than scraping the "Product Code" table
    cell's text, and happens to be the same value anyway."""
    hidden = soup.select_one('input[name="product_id"]')
    if hidden and hidden.get("value"):
        return hidden["value"]

    code_cell = soup.select_one(".product-code")
    return code_cell.get_text(strip=True) if code_cell else None


def _extract_option_groups(soup):
    """Each option group ('Variant', 'Color', ...) is a radio-button block:
        <div class="p-opt-lbl" id="input-optionGROUPID">Color:  <b></b></div>
        <div class="p-opt-vals">
            <input type="radio" value="VALUEID" name="option[GROUPID]" title="Black">
            ...
    Returns [(group_id, group_name, [(value_id, title), ...]), ...] in page order —
    empty list if this product has no variant options at all (a single-variant page)."""
    groups = []
    for opt_div in soup.select(".p-opt-wrap .p-opt"):
        label_div = opt_div.select_one(".p-opt-lbl")
        if label_div is None:
            continue
        group_name = label_div.get_text(strip=True).rstrip(":").strip()

        values = []
        group_id = None
        for radio in opt_div.select('input[type="radio"]'):
            name = radio.get("name", "")
            m = re.match(r"option\[(\w+)\]", name)
            if not m:
                continue
            group_id = m.group(1)
            value_id = radio.get("value")
            title = radio.get("title") or radio.get_text(strip=True)
            if value_id and title:
                values.append((value_id, title))

        if group_id and values:
            groups.append((group_id, group_name, values))

    return groups


def parse_variants(url):
    """For a StarTech product with one or more variant option groups (Color, Variant,
    etc). Queries the same /product/product/variation endpoint the page's own JS calls
    when you click an option, once per combination of every group. A combination that
    genuinely doesn't exist as a real product returns {"error": "error_variation"} with
    no price/stock data at all — that's the only reliable "fake combo" signal. An empty
    "sku" on its own does NOT mean fake: a real variant that's simply out of stock also
    comes back with sku="" but with a real price and stock="Out of Stock" — confirmed by
    directly querying StarTech's own endpoint for a product where a 2x2 option matrix
    had 2 real in-stock combos and 2 real out-of-stock ones, all 4 with genuine prices
    and product photos; only truly invalid option-value pairings return the error shape.

    Returns None if the page has no variant options at all (single-variant product —
    use parse() instead). Returns {"group_names": [...], "variants": [...]} otherwise,
    where each variant is {"labels": [...], "regular": float|None, "sale": float|None,
    "stock": str|None} — "labels" is one title per group, in the same order as
    group_names."""
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    groups = _extract_option_groups(soup)
    if not groups:
        return None

    product_id = _extract_product_id(soup)
    if not product_id:
        raise RuntimeError(f"Could not find a Product Code (product_id) on {url}")

    group_names = [name for (_, name, _) in groups]
    value_lists = [values for (_, _, values) in groups]

    variants = []
    for combo in itertools.product(*value_lists):
        payload = {"product_id": product_id, "enable_emi": "0"}
        for (group_id, _, _), (value_id, _) in zip(groups, combo):
            payload[f"option[{group_id}]"] = value_id

        data = post_form(VARIATION_URL, payload)
        if data.get("error") or not data.get("stock"):
            continue  # this combination doesn't actually exist as a real product

        price_text = data.get("price")
        regular_text = data.get("regular_price")
        variants.append({
            "labels": [title for (_, title) in combo],
            # when a product is on sale, "price" is the discounted one and
            # "regular_price" the original — when it's not, they're identical, so
            # mirror parse()'s convention: no separate "sale" unless it's actually lower
            "regular": parse_amount_text(regular_text) if regular_text else parse_amount_text(price_text),
            "sale": parse_amount_text(price_text) if regular_text and regular_text != price_text else None,
            "stock": _map_stock(data.get("stock")),
        })

    return {"group_names": group_names, "variants": variants}
