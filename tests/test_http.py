import httpx
import pytest

from citrine.http import Client


def make(tmp_path, handler, sleeps):
    return Client(tmp_path, transport=httpx.MockTransport(handler), sleep=sleeps.append)


def test_cache_and_user_agent(tmp_path):
    seen = []

    def handler(req):
        seen.append(req.headers["user-agent"])
        return httpx.Response(200, text="hi")

    c = make(tmp_path, handler, [])
    assert c.get("https://x.test/a") == "hi" and c.get("https://x.test/a") == "hi"
    assert len(seen) == 1 and seen[0].startswith("citrine/")


def test_retries_after_429(tmp_path):
    calls, sleeps = [], []

    def handler(req):
        calls.append(1)
        return httpx.Response(429, headers={"Retry-After": "7"}) if len(calls) == 1 else httpx.Response(200, text="ok")

    assert make(tmp_path, handler, sleeps).get("https://x.test/b") == "ok"
    assert 7.0 in sleeps and len(calls) == 2


def test_gives_up_after_three_429s_without_a_pointless_last_sleep(tmp_path):
    sleeps = []
    c = make(tmp_path, lambda req: httpx.Response(429, headers={"Retry-After": "Wed, 21 Oct 2026 07:28:00 GMT"}), sleeps)
    with pytest.raises(httpx.HTTPStatusError):
        c.get("https://x.test/d")
    assert sleeps == [60, 60]  # date-style Retry-After falls back to 60, and no sleep after the final try


def test_error_is_not_cached(tmp_path):
    c = make(tmp_path, lambda req: httpx.Response(404), [])
    with pytest.raises(httpx.HTTPStatusError):
        c.get("https://x.test/c")
    assert not list(tmp_path.iterdir())
