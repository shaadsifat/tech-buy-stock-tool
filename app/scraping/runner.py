import threading
from concurrent.futures import ThreadPoolExecutor, as_completed

from app import models
from app.config import FETCH_MAX_WORKERS
from app.scraping import registry
from app.scraping.compare import evaluate

_lock = threading.Lock()
_state = {"running": False, "done": 0, "total": 0}


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

    if product_ids:
        models.reset_reviewed_for(product_ids)
    else:
        models.reset_all_reviewed()

    thread = threading.Thread(target=_run_fetch, args=(product_ids,), daemon=True)
    thread.start()
    return True


def _fetch_one_product(product):
    techbuy_link = product["techbuy_link"]
    other_link = product["other_link"]

    techbuy_result = None
    other_result = None
    techbuy_failed = False
    other_failed = False

    try:
        techbuy_result = registry.get_techbuy_parser(techbuy_link)(techbuy_link)
    except Exception:
        techbuy_failed = True

    try:
        other_result = registry.get_other_parser(other_link)(other_link)
    except Exception:
        other_failed = True

    if techbuy_failed and other_failed:
        fetched_status = "Both Prob"
    elif techbuy_failed:
        fetched_status = "TechBuy Prob"
    elif other_failed:
        fetched_status = "Other Prob"
    else:
        fetched_status = "Fetched"

    need_action = None
    updated = None
    if not techbuy_failed and not other_failed:
        tb_stock = techbuy_result.stock
        ot_stock = other_result.stock

        if tb_stock == "Out of Stock" and ot_stock == "Out of Stock":
            # nobody has it — price differences don't matter, nothing to action
            need_action, updated = "No", "Yes"
        elif tb_stock is not None and ot_stock is not None and tb_stock != ot_stock:
            # stock status disagrees between the two sites — flag it directly,
            # regardless of whether either side even has a price
            need_action, updated = "Yes", "No"
        elif techbuy_result.regular is not None and other_result.regular is not None:
            need_action, updated = evaluate(
                techbuy_result.regular, techbuy_result.sale,
                other_result.regular, other_result.sale,
                techbuy_result.stock, other_result.stock,
            )

    data = {
        "techbuy_regular": techbuy_result.regular if techbuy_result else None,
        "techbuy_sale": techbuy_result.sale if techbuy_result else None,
        "techbuy_stock": techbuy_result.stock if techbuy_result else None,
        "other_regular": other_result.regular if other_result else None,
        "other_sale": other_result.sale if other_result else None,
        "other_stock": other_result.stock if other_result else None,
        "need_action": need_action,
        "updated": updated,
        "fetched_status": fetched_status,
    }
    models.upsert_fetch_result(product["id"], data)


def _run_fetch(product_ids=None):
    products = models.get_products_by_ids(product_ids) if product_ids else models.get_all_products()

    with _lock:
        _state["total"] = len(products)

    try:
        with ThreadPoolExecutor(max_workers=FETCH_MAX_WORKERS) as executor:
            futures = [executor.submit(_fetch_one_product, p) for p in products]
            for future in as_completed(futures):
                future.result()  # surfaces unexpected exceptions in logs
                with _lock:
                    _state["done"] += 1
    finally:
        with _lock:
            _state["running"] = False
