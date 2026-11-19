"""Chess.com source. It reads the JSON that chess.com's own website uses (undocumented, so it can
break without warning) and is off unless CITRINE_ENABLE_CHESSCOM=1. Reads live and daily (correspondence) games."""

import datetime as dt
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor

import chess
import chess.pgn
import httpx

from . import SourceError

BASE = "https://www.chess.com"
WORKERS = 4
MONTH = 30 * 86400
MARGIN = 50  # extra games kept around a date range edge, see _in_range
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


def to_pgn(data, game_id, kind="live"):
    """Turn chess.com's game JSON into PGN text. Raises ValueError for games we can't use."""
    try:
        g = data["game"]
        h = {k: str(v) for k, v in g["pgnHeaders"].items()}
        if h.get("FEN", chess.STARTING_FEN) != chess.STARTING_FEN or "Variant" in h:
            raise ValueError("variants and custom start positions are not supported")
        game = chess.pgn.Game()
        game.headers.update({k: v for k, v in h.items() if k not in ("FEN", "SetUp")})
        game.headers["Link"] = f"{BASE}/game/{kind}/{game_id}"
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
    kind, game_id = value.split("/")  # live or daily, both have the same JSON shape
    try:
        data = json.loads(client.get(f"{BASE}/callback/{kind}/game/{game_id}", ttl=MONTH))
        return [to_pgn(data, game_id, kind)], []
    except json.JSONDecodeError:
        raise SourceError(502, "chess.com did not return game data (blocked or changed?)")
    except ValueError as e:
        return [], [f"{kind}/{game_id}: {e}"]


def _date(client, gid):
    """Start date of a game from its (cached) PGN, or None if it has none."""
    pgns, _ = fetch_game(client, gid)
    m = pgns and re.search(r'\[Date "(\d{4})\.(\d\d)\.(\d\d)"\]', pgns[0])
    return dt.date(*map(int, m.groups())) if m else None


def _first(n, ok):
    """First index in 0..n where ok(i) is true, given ok flips from false to true once."""
    lo, hi = 0, n
    while lo < hi:
        mid = (lo + hi) // 2
        lo, hi = (lo, mid) if ok(mid) else (mid + 1, hi)
    return lo


def _in_range(client, ids, since, until):
    """The slice of newest-first `ids` that falls in the range. The list has no dates, so we binary
    search it by reading a few games (about 2*log2(n) requests, cached for the real fetch later).
    ponytail: the list is ordered by finish time and we compare start dates, so we keep a margin of
    MARGIN extra games on each side and filter them exactly afterwards."""
    got = {}
    date = lambda i: got.setdefault(i, _date(client, ids[i]))
    start = _first(len(ids), lambda i: until is None or (date(i) or dt.date.min) <= until)
    stop = _first(len(ids), lambda i: since is not None and (date(i) or dt.date.max) < since)
    return ids[max(0, start - MARGIN) : stop + MARGIN]


def _keep(pgn, since, until):
    m = re.search(r'\[Date "(\d{4})\.(\d\d)\.(\d\d)"\]', pgn)
    d = dt.date(*map(int, m.groups())) if m else None
    return d is None or ((since is None or d >= since) and (until is None or d <= until))


def fetch_profile(client, username, max_games, since=None, until=None, progress=None):
    _enabled()
    ranged = since or until
    ids, page = [], 1
    while ranged or len(ids) < max_games:
        try:
            d = json.loads(client.get(f"{BASE}/callback/games/archive", params={"username": username, "page": page}, ttl=300))
            rows, pages = d["data"], d["meta"]["totalPages"]
        except (json.JSONDecodeError, KeyError, TypeError):
            raise SourceError(502, "chess.com did not return a game list (blocked or changed?)")
        ids += [f"{'live' if r.get('live') else 'daily'}/{r['id']}" for r in rows if r.get("gameType", {}).get("code") == "chess" and not r.get("vsComputer")]
        if not rows or page >= pages:
            break
        page += 1
    blocked = threading.Event()

    def one(gid):
        if blocked.is_set():
            return [], []
        try:
            return fetch_game(client, gid)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            if code != 404:  # a missing game is just missing, anything else means stop hammering
                blocked.set()
            return [], [f"{gid}: chess.com answered {code}"]
        except (SourceError, httpx.HTTPError) as e:
            blocked.set()
            return [], [f"{gid}: {getattr(e, 'message', e)}"]

    if ranged:
        ids = _in_range(client, ids, since, until)
    ids = ids if ranged else ids[:max_games]
    done = []

    def counted(gid):
        r = one(gid)
        done.append(1)
        if progress:
            progress(len(done), len(ids))
        return r

    # ponytail: fixed 4 parallel fetches, one HTTP request per game. Games already fetched are
    # kept even if a later one fails. Move to a background job if one request takes too long.
    with ThreadPoolExecutor(WORKERS) as pool:
        results = list(pool.map(counted, ids))
    pgns = [p for r in results for p in r[0] if _keep(p, since, until)][:max_games]
    errors = [e for r in results for e in r[1]]
    if blocked.is_set():
        errors.append("stopped early: chess.com stopped answering, try again later")
    return pgns, errors
