import hashlib
import os
import time
from pathlib import Path

import httpx


def _retry_after(r):
    try:
        return min(float(r.headers["Retry-After"]), 120)
    except (KeyError, ValueError):  # missing, or an HTTP date instead of seconds
        return 60


class Client:
    """Polite HTTP: identifies itself, backs off when a site says 429, caches responses on disk.
    Thread-safe, so sources can fetch in parallel."""

    def __init__(self, cache_dir=None, transport=None, sleep=time.sleep):
        self.cache = Path(cache_dir or os.environ.get("CITRINE_CACHE", ".cache"))
        contact = os.environ.get("CITRINE_CONTACT", "unset")
        ua = f"citrine/0.1 (+https://github.com/RomanticTinkerer/citrine; contact: {contact})"
        self.http = httpx.Client(headers={"User-Agent": ua}, timeout=30, transport=transport)
        self.sleep = sleep

    def get(self, url, *, accept=None, params=None, ttl=3600) -> str:
        key = hashlib.sha1(f"{url}|{sorted((params or {}).items())}|{accept}".encode()).hexdigest()
        f = self.cache / key
        if f.exists() and time.time() - f.stat().st_mtime < ttl:
            return f.read_text()
        for attempt in range(3):
            r = self.http.get(url, params=params, headers={"Accept": accept} if accept else None)
            if r.status_code != 429 or attempt == 2:
                break
            self.sleep(_retry_after(r))
        r.raise_for_status()
        self.cache.mkdir(parents=True, exist_ok=True)
        f.write_text(r.text)
        return r.text
