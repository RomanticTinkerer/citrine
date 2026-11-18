import httpx
import pytest
from fastapi.testclient import TestClient

from citrine.api import app, get_client, get_store
from citrine.http import Client
from citrine.store import Store

PGN = '[White "Ann"]\n[Black "Bob"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n\n[White "Cy"]\n[Black "Di"]\n\n1. e4 e5 2. Ke3 *\n'


@pytest.fixture
def client():
    store = Store(":memory:")
    app.dependency_overrides[get_store] = lambda: store
    yield TestClient(app)
    app.dependency_overrides.clear()


def test_post_and_read_back(client):
    r = client.post("/games", json={"pgn": PGN}).json()
    assert r["new"] == 1 and len(r["games"]) == 1 and len(r["errors"]) == 1  # second game has an illegal move
    gid = r["games"][0]["id"]
    assert client.post("/games", json={"pgn": PGN}).json()["new"] == 0  # no duplicate
    assert client.get(f"/games/{gid}").json()["white"]["name"] == "Ann"
    assert len(client.get("/games", params={"player": "bob"}).json()) == 1
    assert client.get("/games/nope").status_code == 404


def test_lichess_link(client, tmp_path):
    seen = []

    def handler(req):
        seen.append(str(req.url))
        return httpx.Response(200, text=PGN.split("\n\n[White")[0] + "\n")

    app.dependency_overrides[get_client] = lambda: Client(tmp_path, gap=0, transport=httpx.MockTransport(handler))
    r = client.post("/games", json={"url": "https://lichess.org/abcd1234"}).json()
    assert r["new"] == 1 and r["games"][0]["source"] == "lichess" and r["games"][0]["source_id"] == "abcd1234"
    assert seen[0].startswith("https://lichess.org/game/export/abcd1234")
    assert client.post("/games", json={"url": "https://evil.test/x"}).status_code == 400
    assert client.post("/games", json={"url": "https://lichess.org/@/bob"}).status_code == 400
    assert client.post("/games", json={"url": "https://www.chess.com/game/live/1"}).status_code == 403  # off by default


def test_needs_exactly_one_input(client):
    assert client.post("/games", json={}).status_code == 422
    assert client.post("/games", json={"pgn": "x", "url": "y"}).status_code == 422
