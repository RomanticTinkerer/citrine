import datetime as dt

import httpx

from citrine.http import Client
from citrine.sources import lichess


def test_range_becomes_since_and_until_in_milliseconds(tmp_path):
    seen = {}

    def handler(req):
        seen.update(req.url.params)
        return httpx.Response(200, text="")

    lichess.fetch_profile(Client(tmp_path, transport=httpx.MockTransport(handler)), "bob", 7, dt.date(2020, 1, 1), dt.date(2020, 1, 1))
    assert (seen["max"], seen["since"], seen["until"]) == ("7", "1577836800000", "1577923199999")
