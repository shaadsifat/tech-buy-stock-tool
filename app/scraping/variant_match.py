"""
Classifies each Tech Buy variant against the Other-site's variant options, purely by
matching variant NAMES as an order-independent set — "Red > Silver" and "Silver > Red"
(or with an extra shared layer in any order, e.g. "Red > Silver > USB2" vs
"USB2 > Red > Silver") count as the same variant. Price/stock never factor into whether
something "matches" — only into Need Action once a match is found, via the same
tiered-tolerance comparison used everywhere else in this app.

Per-variant outcomes:
    FOUND      — the variant name exists on both sites. Need Action/Reviewed follow the
                 normal price/stock comparison rules, same as a single-variant product.
    NOT_FOUND  — exists on Tech Buy (In Stock), not on the other site at all.
                 Need Action = Yes, Reviewed stays editable.
    FOUND_TB   — exists on Tech Buy (Out of Stock), not on the other site at all.
                 Need Action = No, Reviewed auto-locks (nothing to review — nobody's
                 selling it anywhere to compare against).
    FOUND_OT   — exists on the other site, not on Tech Buy at all. Gets a real variant
                 row of its own (see models.sync_found_ot_variants) — same shape as a
                 Tech Buy variant row, just with no Tech Buy price/stock. Need Action =
                 Yes, Reviewed stays editable.

Product-level tab, evaluated as a strict waterfall (checked in order, first match wins
— a product only ever lands in exactly one of these; see models._MATCH_STATUS_CASE):
    1. EXACT_MATCH          — every variant is FOUND or FOUND_TB.
    2. VARIANT_NOT_FOUND     — (only reachable if not #1) at least one NOT_FOUND variant.
    3. MISSING_FROM_TECHBUY  — (only reachable if not #1/#2) at least one FOUND_OT variant.
"""

FOUND = "found"
NOT_FOUND = "not_found"
FOUND_TB = "found_tb"
FOUND_OT = "found_ot"


def _normalize(text):
    return text.strip().lower()


def _label_set(labels):
    """A variant's option values as an order-independent set — layer ordering
    differences between the two sites don't count as a mismatch."""
    return frozenset(_normalize(v) for v in labels)


def classify_variants(techbuy_variants, other_data):
    """techbuy_variants: this product's variants, as [{"path": "Red > Silver",
    "stock": "In Stock"|"Out of Stock"|None}, ...]. other_data: the dict returned by a
    site parser's parse_variants(), or None/empty if nothing was fetched.

    Returns (techbuy_results, found_ot_variants):
      techbuy_results — list, same order/length as techbuy_variants, of
        {"path": str, "status": FOUND|NOT_FOUND|FOUND_TB, "other": {...}|None}
        "other" is the matched other-site data (regular/sale/stock), only present for
        FOUND.
      found_ot_variants — other-site variants with no Tech Buy counterpart at all, as
        [{"labels": [...], "regular", "sale", "stock"}, ...] — each becomes its own real
        variant row (see models.sync_found_ot_variants)."""
    other_variants = (other_data or {}).get("variants") or []
    other_sets = [(_label_set(v["labels"]), v) for v in other_variants]

    def find_match(path):
        tb_set = _label_set(path.split(" > "))
        return next((v for o_set, v in other_sets if o_set == tb_set), None)

    techbuy_results = []
    matched_other_sets = set()
    for tv in techbuy_variants:
        path = tv["path"]
        match = find_match(path)
        if match is not None:
            matched_other_sets.add(_label_set(match["labels"]))
            techbuy_results.append({"path": path, "status": FOUND, "other": match})
        elif tv.get("stock") == "Out of Stock":
            techbuy_results.append({"path": path, "status": FOUND_TB, "other": None})
        else:
            techbuy_results.append({"path": path, "status": NOT_FOUND, "other": None})

    found_ot_variants = [v for v in other_variants if _label_set(v["labels"]) not in matched_other_sets]

    return techbuy_results, found_ot_variants
