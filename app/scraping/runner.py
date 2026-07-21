import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import models
from app.config import FETCH_MAX_WORKERS
from app.scraping import base
from app.scraping import registry
from app.scraping.base import FetchResult
from app.scraping.compare import evaluate
from app.scraping.variant_match import classify_variants, FOUND, FOUND_TB

_lock = threading.Lock()
_state = {"running": False, "done": 0, "total": 0, "stopped": False}
_stop_event = threading.Event()


def get_status():
    with _lock:
        return dict(_state)


def start_fetch(product_ids=None):
    """product_ids=None fetches every product; a list scopes the run to just those."""
    with _lock:
        if _state["running"]:
            return False
        _state["running"] = True
        _state["done"] = 0
        _state["total"] = 0
        _state["stopped"] = False

    _stop_event.clear()
    base.clear_abort()

    if product_ids:
        models.reset_reviewed_for(product_ids)
        models.reset_variant_reviewed_for(product_ids)
    else:
        models.reset_all_reviewed()

    thread = threading.Thread(target=_run_fetch, args=(product_ids,), daemon=True)
    thread.start()
    return True


def stop_fetch():
    """Requests the running fetch to stop. Products already in flight still finish
    (an HTTP request already underway can't be interrupted); anything not yet
    started is skipped."""
    with _lock:
        if not _state["running"]:
            return False
        _state["stopped"] = True
    _stop_event.set()
    base.request_abort()
    return True


def _need_action_for(techbuy_regular, techbuy_sale, techbuy_stock, other_regular, other_sale, other_stock):
    if techbuy_stock == "Out of Stock" and other_stock == "Out of Stock":
        return "No", "Yes"
    if techbuy_stock is not None and other_stock is not None and techbuy_stock != other_stock:
        return "Yes", "No"
    if techbuy_regular is not None and other_regular is not None:
        return evaluate(techbuy_regular, techbuy_sale, other_regular, other_sale, techbuy_stock, other_stock)
    return None, None


def _fetch_variant_product_matched(product, other_link, variants, variant_parser):
    """Real path: the other site has a variant-aware parser, so each Tech Buy variant
    gets matched against the other site's actual option combinations by name (see
    app.scraping.variant_match). FOUND gets real price/stock and the normal Need Action
    comparison; NOT_FOUND/FOUND_TB are informational states with no price to compare.
    Any other-site variant with no Tech Buy counterpart (FOUND_OT) becomes its own real
    variant row via models.sync_found_ot_variants."""
    try:
        other_data = variant_parser(other_link)
    except Exception:
        models.sync_found_ot_variants(product["id"], [])
        for v in variants:
            models.update_variant_other_fetch_result(v["id"], {
                "other_regular": None, "other_sale": None, "other_stock": None,
                "need_action": None, "updated": None, "fetched_status": "Fetch Problem",
                "match_status": None, "match_note": None,
            })
        return

    techbuy_variants = [{"path": v["variant_path"], "stock": v["techbuy_stock"]} for v in variants]
    results, found_ot_variants = classify_variants(techbuy_variants, other_data)
    models.sync_found_ot_variants(product["id"], found_ot_variants)

    for v, result in zip(variants, results):
        status = result["status"]
        other = result["other"]

        if status == FOUND and other is not None:
            need_action, updated = _need_action_for(
                v["techbuy_regular"], v["techbuy_sale"], v["techbuy_stock"],
                other["regular"], other["sale"], other["stock"],
            )
            models.update_variant_other_fetch_result(v["id"], {
                "other_regular": other["regular"],
                "other_sale": other["sale"],
                "other_stock": other["stock"],
                "need_action": need_action,
                "updated": updated,
                "fetched_status": "Fetched",
                "match_status": status,
                "match_note": None,
            })
        elif status == FOUND_TB:
            # Out of Stock on Tech Buy, not sold on the other site either — nothing to
            # compare. need_action="No" reuses the existing auto-review-lock behavior
            # already built into update_variant_other_fetch_result.
            models.update_variant_other_fetch_result(v["id"], {
                "other_regular": None, "other_sale": None, "other_stock": None,
                "need_action": "No", "updated": None, "fetched_status": "Fetched",
                "match_status": status,
                "match_note": None,
            })
        else:  # NOT_FOUND
            models.update_variant_other_fetch_result(v["id"], {
                "other_regular": None, "other_sale": None, "other_stock": None,
                "need_action": "Yes", "updated": None, "fetched_status": "Fetched",
                "match_status": status,
                "match_note": None,
            })


def _fetch_variant_product_unmatched(product, other_link, variants):
    """Stopgap for sites without a variant-aware parser yet: applies the one scraped
    price/stock to every variant, comparing it against each variant's own Tech Buy
    price. No match_status is set here — there was no real per-variant matching
    attempted, so there's nothing meaningful to classify."""
    models.sync_found_ot_variants(product["id"], [])
    try:
        other_result = registry.get_other_parser(other_link)(other_link)
    except Exception:
        for v in variants:
            models.update_variant_other_fetch_result(v["id"], {
                "other_regular": None, "other_sale": None, "other_stock": None,
                "need_action": None, "updated": None, "fetched_status": "Fetch Problem",
                "match_status": None, "match_note": None,
            })
        return

    for v in variants:
        need_action, updated = _need_action_for(
            v["techbuy_regular"], v["techbuy_sale"], v["techbuy_stock"],
            other_result.regular, other_result.sale, other_result.stock,
        )
        models.update_variant_other_fetch_result(v["id"], {
            "other_regular": other_result.regular,
            "other_sale": other_result.sale,
            "other_stock": other_result.stock,
            "need_action": need_action,
            "updated": updated,
            "fetched_status": "Fetched",
            "match_status": None,
            "match_note": None,
        })


def _fetch_variant_product(product, other_link):
    variants = models.get_variants_for_product(product["id"])
    if not variants:
        return False

    if not other_link:
        models.sync_found_ot_variants(product["id"], [])
        for v in variants:
            models.update_variant_other_fetch_result(v["id"], {
                "other_regular": None, "other_sale": None, "other_stock": None,
                "need_action": None, "updated": None, "fetched_status": None,
                "match_status": None, "match_note": None,
            })
        return True

    variant_parser = registry.get_variant_parser(other_link)
    if variant_parser is not None:
        _fetch_variant_product_matched(product, other_link, variants, variant_parser)
    else:
        _fetch_variant_product_unmatched(product, other_link, variants)
    return True


def _fetch_one_product(product, throttle=True):
    if _stop_event.is_set():
        return

    base.set_throttle_enabled(throttle)

    other_link = product["other_link"]

    if _fetch_variant_product(product, other_link):
        return

    if not other_link:
        # Tech Buy's own price/stock always comes from the Shopify catalog sync
        # (get_product_api_call.py) now, not scraping — nothing to fetch here until
        # this product has an Other-site link paired.
        models.update_other_fetch_result(product["id"], {
            "other_regular": None, "other_sale": None, "other_stock": None,
            "need_action": None, "updated": None, "fetched_status": None,
        })
        return

    # Tech Buy shows this as a single-variant product, but that says nothing about the
    # OTHER site — it may have grown real variants since this pairing was made. If its
    # domain has a variant-aware parser, check there first: 2+ real variants there means
    # a single scraped price can't be trusted (which one would it even be?), so this gets
    # flagged instead of silently grabbing whichever price the page defaults to. Exactly
    # 1 real variant there is the normal case — reuse that single result directly rather
    # than making a second request. Single Product List only; Variant Products already
    # does real per-variant matching regardless.
    variant_parser = registry.get_variant_parser(other_link)
    other_result = None

    if variant_parser is not None:
        try:
            other_data = variant_parser(other_link)
        except Exception:
            models.update_other_fetch_result(product["id"], {
                "other_regular": None, "other_sale": None, "other_stock": None,
                "need_action": None, "updated": None, "fetched_status": "Fetch Problem",
            })
            return

        real_variants = (other_data or {}).get("variants") or []
        if len(real_variants) > 1:
            models.update_other_fetch_result(product["id"], {
                "other_regular": None, "other_sale": None, "other_stock": "Variant Found",
                "need_action": "Yes", "updated": None, "fetched_status": "Fetched",
            })
            return
        if len(real_variants) == 1:
            v = real_variants[0]
            other_result = FetchResult(regular=v["regular"], sale=v["sale"], stock=v["stock"])
        # else: no variant options there at all — falls through to the plain parser below

    if other_result is None:
        try:
            other_result = registry.get_other_parser(other_link)(other_link)
        except Exception:
            models.update_other_fetch_result(product["id"], {
                "other_regular": None, "other_sale": None, "other_stock": None,
                "need_action": None, "updated": None, "fetched_status": "Fetch Problem",
            })
            return

    existing = models.get_fetch_result(product["id"])
    techbuy_regular = existing["techbuy_regular"] if existing else None
    techbuy_sale = existing["techbuy_sale"] if existing else None
    techbuy_stock = existing["techbuy_stock"] if existing else None

    need_action = None
    updated = None

    if techbuy_stock == "Out of Stock" and other_result.stock == "Out of Stock":
        # nobody has it — price differences don't matter, nothing to action
        need_action, updated = "No", "Yes"
    elif techbuy_stock is not None and other_result.stock is not None and techbuy_stock != other_result.stock:
        # stock status disagrees between the two sites — flag it directly,
        # regardless of whether either side even has a price
        need_action, updated = "Yes", "No"
    elif techbuy_regular is not None and other_result.regular is not None:
        need_action, updated = evaluate(
            techbuy_regular, techbuy_sale,
            other_result.regular, other_result.sale,
            techbuy_stock, other_result.stock,
        )

    models.update_other_fetch_result(product["id"], {
        "other_regular": other_result.regular,
        "other_sale": other_result.sale,
        "other_stock": other_result.stock,
        "need_action": need_action,
        "updated": updated,
        "fetched_status": "Fetched",
    })


def _run_fetch(product_ids=None):
    products = models.get_products_by_ids(product_ids) if product_ids else models.get_all_products()
    throttle = len(products) > 1  # a lone manual fetch isn't a burst — no need to pace it

    with _lock:
        _state["total"] = len(products)

    try:
        with ThreadPoolExecutor(max_workers=FETCH_MAX_WORKERS) as executor:
            futures = [executor.submit(_fetch_one_product, p, throttle) for p in products]
            for future in as_completed(futures):
                future.result()  # surfaces unexpected exceptions in logs
                with _lock:
                    _state["done"] += 1
    finally:
        with _lock:
            _state["running"] = False
