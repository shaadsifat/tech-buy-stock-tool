import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
DB_PATH = os.path.join(DATA_DIR, "app.db")

PAGE_SIZE_CHOICES = [20, 50, 100]
DEFAULT_PAGE_SIZE = 20

# Fetching is network I/O-bound (waiting on HTTP responses), not CPU-bound, so more
# workers than CPU cores is normal and fine. Still scaled off the machine's actual
# core count and capped well below what any modern PC can handle comfortably, so it
# never floods a low-end machine's connection/RAM with too many simultaneous
# requests, and never spawns an excessive thread count on a high-core-count one either.
FETCH_MAX_WORKERS = min(12, max(4, (os.cpu_count() or 4) * 2))
