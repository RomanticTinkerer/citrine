import hashlib
import io
from datetime import datetime, timezone

import chess
import chess.pgn

from .models import Game, Player


def _elo(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def parse_pgn(text, source="pgn", source_url=None, source_id=None):
    """Parse PGN text into Games. Returns (games, errors); bad games are reported, not raised."""
    games, errors = [], []
    stream = io.StringIO(text)
    n = 0
    while (g := chess.pgn.read_game(stream)) is not None:
        n += 1
        h = g.headers
        if h.get("Variant", "Standard").lower() not in ("standard", "chess"):
            errors.append(f"game {n}: variant {h['Variant']} is not supported")
            continue
        if g.errors:
            errors.append(f"game {n}: {g.errors[0]}")
            continue
        if g.board().fen() != chess.STARTING_FEN:
            errors.append(f"game {n}: custom start position is not supported")
            continue
        nodes = list(g.mainline())
        if not nodes:
            errors.append(f"game {n}: no moves")
            continue
        moves = [x.move.uci() for x in nodes]
        white, black = h.get("White", "?"), h.get("Black", "?")
        date = h.get("UTCDate") or h.get("Date")
        date = None if not date or "?" in date else date.replace(".", "-")
        gid = hashlib.sha1(f"{white}|{black}|{date}|{' '.join(moves)}".encode()).hexdigest()
        event = h.get("Event", "").lower()  # lichess says "Rated blitz game" / "Casual ..."
        rated = True if event.startswith("rated") else False if event.startswith("casual") else None
        site = h.get("Link") or h.get("Site", "")
        games.append(
            Game(
                id=gid,
                source=source,
                source_url=source_url or (site if site.startswith("http") else None),
                source_id=source_id,
                white=Player(name=white, elo=_elo(h.get("WhiteElo"))),
                black=Player(name=black, elo=_elo(h.get("BlackElo"))),
                result=h.get("Result", "*"),
                termination=h.get("Termination"),
                time_control=h.get("TimeControl"),
                rated=rated,
                date=date,
                eco=h.get("ECO"),
                opening=h.get("Opening"),
                moves_uci=moves,
                clocks=[x.clock() for x in nodes],
                pgn=str(g),
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        )
    if n == 0:
        errors.append("no games found")
    return games, errors
