import json
from pathlib import Path

import chess
import httpx
import pytest

from citrine.http import Client
from citrine.sources import SourceError, chesscom
from citrine.validate import parse_pgn

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "chesscom_live.json").read_text())


def client(tmp_path, handler):
    return Client(tmp_path, transport=httpx.MockTransport(handler))


def test_decoder_reaches_the_known_final_position():
    board = chess.Board()
    for m in chesscom.decode_moves(FIXTURE["game"]["moveList"]):  # includes a promotion
        board.push_uci(m)
    assert board.fen() == "2Q5/k1R2N2/p4K2/P7/3r1p2/8/6P1/8 b - - 2 60"


def test_off_by_default(tmp_path, monkeypatch):
    monkeypatch.delenv("CITRINE_ENABLE_CHESSCOM", raising=False)
    with pytest.raises(SourceError) as e:
        chesscom.fetch_game(client(tmp_path, lambda r: httpx.Response(500)), "live/1")
    assert e.value.status == 403


def test_game_to_valid_record(tmp_path, monkeypatch):
    monkeypatch.setenv("CITRINE_ENABLE_CHESSCOM", "1")
    pgns, errors = chesscom.fetch_game(client(tmp_path, lambda r: httpx.Response(200, json=FIXTURE)), "live/1")
    games, errs = parse_pgn(pgns[0], source="chesscom", source_id="live/1")
    g = games[0]
    assert not errors and not errs and len(g.moves_uci) == 119
    assert g.white.elo == 3455 and g.clocks[0] == 180 and g.clocks[2] == 178.7
    assert g.source_url == "https://www.chess.com/game/live/1"


def test_profile_pages_and_filters(tmp_path, monkeypatch):
    monkeypatch.setenv("CITRINE_ENABLE_CHESSCOM", "1")
    seen = []

    def handler(req):
        seen.append(req.url.path)
        if req.url.path == "/callback/games/archive":
            rows = [{"id": 1, "live": True, "gameType": {"code": "chess"}}, {"id": 2, "live": True, "gameType": {"code": "chess960"}}, {"id": 3, "live": False, "gameType": {"code": "chess"}}]
            return httpx.Response(200, json={"data": rows, "meta": {"totalPages": 1}})
        return httpx.Response(200, json=FIXTURE)

    pgns, errors = chesscom.fetch_profile(client(tmp_path, handler), "someone", 10)
    assert len(pgns) == 1 and not errors
    assert seen == ["/callback/games/archive", "/callback/live/game/1"]


def test_one_bad_game_does_not_lose_the_rest(tmp_path, monkeypatch):
    monkeypatch.setenv("CITRINE_ENABLE_CHESSCOM", "1")

    def handler(req):
        if req.url.path == "/callback/games/archive":
            rows = [{"id": i, "live": True, "gameType": {"code": "chess"}} for i in (1, 2, 3)]
            return httpx.Response(200, json={"data": rows, "meta": {"totalPages": 1}})
        gid = req.url.path.rsplit("/", 1)[1]
        return {"1": httpx.Response(200, json=FIXTURE), "2": httpx.Response(404)}.get(gid, httpx.Response(200, json=FIXTURE))

    pgns, errors = chesscom.fetch_profile(client(tmp_path, handler), "someone", 10)
    assert len(pgns) == 2 and errors == ["live/2: chess.com answered 404"]  # 404 is just a missing game

    def flaky(req):
        if req.url.path.endswith("/2"):
            return httpx.Response(503)
        return handler(req)

    chesscom.WORKERS = 1  # keep the order fixed for this check
    try:
        pgns, errors = chesscom.fetch_profile(client(tmp_path / "b", flaky), "someone", 10)
    finally:
        chesscom.WORKERS = 4
    assert len(pgns) == 1 and "live/2: chess.com answered 503" in errors and errors[-1].startswith("stopped early")


def test_blocked_page_is_a_clean_error(tmp_path, monkeypatch):
    monkeypatch.setenv("CITRINE_ENABLE_CHESSCOM", "1")
    with pytest.raises(SourceError) as e:
        chesscom.fetch_game(client(tmp_path, lambda r: httpx.Response(200, text="<html>")), "live/9")
    assert e.value.status == 502
