def get_tolerance(price):
    """Tiered tolerance based on Tech Buy's price (sale price if present, else regular)."""
    if price >= 150:
        return 3
    if price >= 100:
        return 1
    return 0


def evaluate(tb_regular, tb_sale, other_regular, other_sale):
    """Returns (need_action, updated) as 'Yes'/'No' strings.

    Rules:
    - If Tech Buy has a sale price and Other has a sale price: sale vs sale uses the
      tiered tolerance (primary check); regular vs regular gets a flat $100 tolerance.
      Need Action = Yes if either check fails.
    - Otherwise: compare regular vs regular using the tiered tolerance (based on
      Tech Buy's regular price).
    """
    if tb_sale is not None and other_sale is not None:
        sale_tolerance = get_tolerance(tb_sale)
        sale_ok = abs(tb_sale - other_sale) <= sale_tolerance
        regular_ok = abs(tb_regular - other_regular) <= 100
        ok = sale_ok and regular_ok
    else:
        tolerance = get_tolerance(tb_regular)
        ok = abs(tb_regular - other_regular) <= tolerance

    return ("No", "Yes") if ok else ("Yes", "No")
