import os
from requests_cache import CachedSession

dirname = os.path.dirname(__file__)
# YTCT_CACHE_FILE lets read-only installs (e.g. the Nix store) keep the cache elsewhere
CACHE_FILE_PATH = os.environ.get("YTCT_CACHE_FILE") or os.path.join(dirname, "requests_cache.sqlite")

requests_cache = CachedSession(allowable_methods=("GET", "POST"), cache_name=CACHE_FILE_PATH)
