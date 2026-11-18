"""Chess.com source. It reads the JSON that chess.com's own website uses (undocumented, so it can
break without warning) and is off unless CITRINE_ENABLE_CHESSCOM=1. Live games only for now."""

import json
import os
import threading
from concurrent.futures import ThreadPoolExecutor

import chess
import chess.pgn
import httpx

from . import SourceError

BASE = "https://www.chess.com"
WORKERS = 4
MONTH = 30 * 86400
# chess.com packs each move into 2 characters: from-square index, then to-square index.
# Promotions use to-index above 63. Verified against chess.com's own PGN for a real game.
TCN = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789!?{~}(^)[_]@#$,./&-*++="


def _enabled():
    if os.environ.get("CITRINE_ENABLE_CHESSCOM") != "1":
        raise SourceError(403, "the chess.com source is off. Set CITRINE_ENABLE_CHESSCOM=1 to turn it on.")


def decode_moves(s):
    sq = lambda i: "abcdefgh"[i % 8] + str(i // 8 + 1)
    out = []
    for i in range(0, len(s), 2):
        a, b = TCN.index(s[i]), TCN.index(s[i + 1])
        promo = ""
        if b > 63:
            promo = "qnrbkp"[(b - 64) // 3]
            b = a + (-8 if a < 16 else 8) + ((b - 1) % 3) - 1
        out.append(sq(a) + sq(b) + promo)
    return out


def to_pgn(data, game_id):
    """Turn chess.com's game JSON into PGN text. Raises ValueError for games we can't use."""
    try:
        g = data["game"]
        h = {k: str(v) for k, v in g["pgnHeaders"].items()}
        if h.get("FEN", chess.STARTING_FEN) != chess.STARTING_FEN or "Variant" in h:
            raise ValueError("variants and custom start positions are not supported")
        game = chess.pgn.Game()
        game.headers.update({k: v for k, v in h.items() if k not in ("FEN", "SetUp")})
        game.headers["Link"] = f"{BASE}/game/live/{game_id}"
        stamps = (g.get("moveTimestamps") or "").strip(",").split(",")
        board, node = chess.Board(), game
        for i, uci in enumerate(decode_moves(g["moveList"])):
            m = chess.Move.from_uci(uci)
            if m not in board.legal_moves:
                raise ValueError("could not decode the move list")
            board.push(m)
            node = node.add_variation(m)
            if i < len(stamps) and stamps[i]:
                node.set_clock(int(stamps[i]) / 10)  # chess.com gives tenths of a second left
        return str(game)
    except (KeyError, TypeError, IndexError):
        raise ValueError("unexpected response shape from chess.com")


def fetch_game(client, value):
    _enabled()
    kind, game_id = value.split("/")
    if kind != "live":
        raise SourceError(501, "chess.com daily games are not supported yet")
    try:
        data = json.loads(client.get(f"{BASE}/callback/live/game/{game_id}", ttl=MONTH))
        return [to_pgn(data, game_id)], []
    except json.JSONDecodeError:
        raise SourceError(502, "chess.com did not return game data (blocked or changed?)")
    except ValueError as e:
        return [], [f"live/{game_id}: {e}"]


def fetch_profile(client, username, max_games):
    _enabled()
    ids, page = [], 1
    while len(ids) < max_games:
        try:
            d = json.loads(client.get(f"{BASE}/callback/games/archive", params={"username": username, "gameType": "live", "page": page}, ttl=300))
            rows, pages = d["data"], d["meta"]["totalPages"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise SourceError(502, "chess.com did not return a game list (blocked or changed?)")
        ids += [r["id"] for r in rows if r.get("live") and r.get("gameType", {}).get("code") == "chess" and not r.get("vsComputer")]
        if not rows or page >= pages:
            break
        page += 1
    blocked = threading.Event()

    def one(gid):
        if blocked.is_set():
            return [], []
        try:
            return fetch_game(client, f"live/{gid}")
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code != 404:  # a missing game is just missing, anything else means stop hammering
                blocked.set()
            return [], [f"live/{gid}: chess.com answered {code}"]
        except (SourceError, httpx.HTTPError) as e:
            blocked.set()
            return [], [f"live/{gid}: {getattr(e, 'message', e)}"]

    # ponytail: fixed 4 parallel fetches, one HTTP request per game. Games already fetched are
    # kept even if a later one fails. Move to a background job if one request takes too long.
    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(one, ids[:max_games]))
    pgns = [p for r in results for p in r[0]]
    errors = [e for r in results for e in r[1]]
    if blocked.is_set():
        errors.append("stopped early: chess.com stopped answering, try again later")
    return pgns, errors
