import hashlib
import os
import threading
import time
from pathlib import Path

import httpx

DAY = 86400


class Client:
    """Polite HTTP: identifies itself, spaces out requests, backs off on 429, caches responses on disk."""

    def __init__(self, cache_dir=None, gap=1.0, transport=None, sleep=time.sleep):
        self.cache = Path(cache_dir or os.environ.get("CITRINE_CACHE", ".cache"))
        contact = os.environ.get("CITRINE_CONTACT", "unset")
        ua = f"citrine/0.1 (+https://github.com/RomanticTinkerer/citrine; contact: {contact})"
        self.http = httpx.Client(headers={"User-Agent": ua}, timeout=30, transport=transport)
        self.gap, self.sleep = gap, sleep
        self.last = 0.0
        # ponytail: one global lock serialises every request. That also meets Lichess's
        # one-at-a-time rule. Go per-host if throughput ever matters.
        self.lock = threading.Lock()

    def get(self, url, *, accept=None, params=None, ttl=3600) -> str:
        key = hashlib.sha1(f"{url}|{sorted((params or {}).items())}|{accept}".encode()).hexdigest()
        f = self.cache / key
        if f.exists() and time.time() - f.stat().st_mtime < ttl:
            return f.read_text()
        with self.lock:
            for _ in range(3):
                wait = self.gap - (time.monotonic() - self.last)
                if wait > 0:
                    self.sleep(wait)
                r = self.http.get(url, params=params, headers={"Accept": accept} if accept else None)
                self.last = time.monotonic()
                if r.status_code != 429:
                    break
                self.sleep(min(float(r.headers.get("Retry-After", 60)), 120))
        r.raise_for_status()
        self.cache.mkdir(parents=True, exist_ok=True)
        f.write_text(r.text)
        return r.text
