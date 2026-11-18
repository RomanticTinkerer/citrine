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


def san_list(uci_moves):
    board, out = chess.Board(), []
    for u in uci_moves:
        m = chess.Move.from_uci(u)
        out.append(board.san(m))
        board.push(m)
    return out


def numbered(san):
    """['e4', 'e5', 'Nf3'] -> '1. e4 e5 2. Nf3'"""
    return " ".join(f"{i // 2 + 1}. {m}" if i % 2 == 0 else m for i, m in enumerate(san))


def parse_pgn(text, source="pgn", source_url=None, source_id=None):
    """Parse PGN text into Games. Returns (games, errors); bad games are reported, not raised."""
    games, errors = [], []
    stream = io.StringIO(text)
    n = 0
    while (g := chess.pgn.read_game(stream)) is not None:
        n += 1
        h = g.headers
        label = h.get("Link") or f"game {n}"  # say which game was bad
        if h.get("Variant", "Standard").lower() not in ("standard", "chess"):
            errors.append(f"{label}: variant {h['Variant']} is not supported")
            continue
        if g.errors:
            errors.append(f"{label}: {g.errors[0]}")
            continue
        if g.board().fen() != chess.STARTING_FEN:
            errors.append(f"{label}: custom start position is not supported")
            continue
        nodes = list(g.mainline())
        if not nodes:
            errors.append(f"{label}: no moves")
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
                moves_san=[x.san() for x in nodes],
                clocks=[x.clock() for x in nodes],
                pgn=str(g),
                fetched_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
            )
        )
    if n == 0:
        errors.append("no games found")
    return games, errors
