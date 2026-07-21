import random
import re
import threading
import time
from urllib.parse import urlparse

import requests

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}

REQUEST_TIMEOUT = 15

# Every "Other website" domain gets a polite baseline gap between requests so no
# site sees a burst of concurrent automated requests during a fetch run.
DEFAULT_MIN_INTERVAL = 1.0
DOMAIN_MIN_INTERVAL = {}
# Randomized +/- so requests don't land on a perfectly regular, bot-like cadence — a
# fresh random value up to this ratio each time (e.g. 1s +/- up to 15%, never a fixed
# +15% every time), via random.uniform(-jitter, jitter) below.
JITTER_RATIO = 0.15

_domain_locks = {}
_domain_locks_guard = threading.Lock()
_domain_last_request = {}

# A lone, manually-triggered single-product fetch isn't a burst — nothing to
# protect against — so it can skip the throttle wait entirely. Thread-local so
# it only applies to the specific worker handling that one-off fetch, not any
# concurrent batch run happening on other threads.
_thread_local = threading.local()


def set_throttle_enabled(enabled):
    _thread_local.throttle_enabled = enabled


def _throttle_enabled():
    return getattr(_thread_local, "throttle_enabled", True)

# Lets runner.stop_fetch() interrupt a request that's mid-throttle-wait, instead
# of it blindly finishing its full wait + HTTP call before the stop takes effect.
_abort_event = threading.Event()


class FetchAborted(Exception):
    """Raised when a fetch is interrupted mid-throttle-wait by a Stop Fetching request."""


def request_abort():
    _abort_event.set()


def clear_abort():
    _abort_event.clear()


def _domain_of(url):
    netloc = urlparse(url).netloc.lower()
    if netloc.startswith("www."):
        netloc = netloc[4:]
    return netloc


def _get_domain_lock(domain):
    with _domain_locks_guard:
        if domain not in _domain_locks:
            _domain_locks[domain] = threading.Lock()
        return _domain_locks[domain]


def _interval_for(domain):
    base = DOMAIN_MIN_INTERVAL.get(domain, DEFAULT_MIN_INTERVAL)
    jitter = base * JITTER_RATIO
    return base + random.uniform(-jitter, jitter)


def _sleep_interruptible(seconds):
    """Sleeps in short slices so an abort request lands within ~0.2s instead of
    waiting out the full throttle interval."""
    deadline = time.monotonic() + seconds
    while True:
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return
        if _abort_event.wait(min(remaining, 0.2)):
            raise FetchAborted()


def _throttled_get(url, domain):
    if _abort_event.is_set():
        raise FetchAborted()

    lock = _get_domain_lock(domain)
    with lock:
        if _abort_event.is_set():
            raise FetchAborted()
        if _throttle_enabled():
            elapsed = time.monotonic() - _domain_last_request.get(domain, 0)
            interval = _interval_for(domain)
            if elapsed < interval:
                _sleep_interruptible(interval - elapsed)
        try:
            return requests.get(url, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        finally:
            _domain_last_request[domain] = time.monotonic()


def fetch_html(url):
    """Fetch a page's HTML. Raises on failure (caller is responsible for catching)."""
    domain = _domain_of(url)
    response = _throttled_get(url, domain)

    if response.status_code == 429:
        retry_after = response.headers.get("retry-after")
        try:
            wait = float(retry_after) if retry_after else _interval_for(domain) * 4
        except ValueError:
            wait = _interval_for(domain) * 4
        _sleep_interruptible(wait)
        response = _throttled_get(url, domain)

    response.raise_for_status()
    return response.text


def _throttled_post(url, domain, data):
    if _abort_event.is_set():
        raise FetchAborted()

    lock = _get_domain_lock(domain)
    with lock:
        if _abort_event.is_set():
            raise FetchAborted()
        if _throttle_enabled():
            elapsed = time.monotonic() - _domain_last_request.get(domain, 0)
            interval = _interval_for(domain)
            if elapsed < interval:
                _sleep_interruptible(interval - elapsed)
        try:
            return requests.post(url, data=data, headers=DEFAULT_HEADERS, timeout=REQUEST_TIMEOUT)
        finally:
            _domain_last_request[domain] = time.monotonic()


def post_form(url, data):
    """POST a form body, return parsed JSON. Shares the same per-domain throttle/lock as
    fetch_html — a multi-layer variant product can mean many POSTs to the same domain in
    a row (one per option combination), so they need to stay just as politely paced."""
    domain = _domain_of(url)
    response = _throttled_post(url, domain, data)
    response.raise_for_status()
    return response.json()


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
