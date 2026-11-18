import sqlite3
import threading

from .models import Game
from .validate import numbered, san_list

# Readable columns first so the table makes sense in any SQLite viewer. `data` is the full JSON record.
COLS = ("white", "black", "result", "date", "moves", "pgn", "data")


def _vals(g: Game):
    return (g.white.name, g.black.name, g.result, g.date, numbered(g.moves_san), g.pgn, g.model_dump_json())


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()  # ponytail: one connection plus a lock, fine until heavy concurrent writes
        self.db.execute("create table if not exists games(id text primary key, source text)")
        have = {r[1] for r in self.db.execute("pragma table_info(games)")}
        for c in COLS:
            if c not in have:
                self.db.execute(f"alter table games add column {c} text")
        # older databases only had id, source, lowercased names and data: fill in the new columns
        for gid, data in self.db.execute("select id, data from games where pgn is null").fetchall():
            g = Game.model_validate_json(data)
            g.moves_san = g.moves_san or san_list(g.moves_uci)
            self.db.execute(f"update games set {', '.join(c + '=?' for c in COLS)} where id=?", (*_vals(g), gid))
        self.db.commit()

    def add_many(self, games) -> int:
        """Insert games with a single commit. Returns how many were new."""
        sql = f"insert or ignore into games(id, source, {', '.join(COLS)}) values ({', '.join('?' * (len(COLS) + 2))})"
        with self.lock:
            n = sum(self.db.execute(sql, (g.id, g.source, *_vals(g))).rowcount for g in games)
            self.db.commit()
        return n

    def add(self, g: Game) -> bool:
        return self.add_many([g]) == 1

    def get(self, gid):
        with self.lock:
            row = self.db.execute("select data from games where id=?", (gid,)).fetchone()
        return Game.model_validate_json(row[0]) if row else None

    def _where(self, source, player):
        sql, args = " where 1=1", []
        if source:
            sql += " and source=?"
            args.append(source)
        if player:
            sql += " and (lower(white)=? or lower(black)=?)"
            args += [player.lower()] * 2
        return sql, args

    def list(self, source=None, player=None, limit=50, offset=0):
        sql, args = self._where(source, player)
        with self.lock:
            rows = self.db.execute(
                f"select data from games{sql} order by rowid limit ? offset ?", [*args, limit, offset]
            ).fetchall()
        return [Game.model_validate_json(r[0]) for r in rows]

    def export(self, source=None, fmt="jsonl"):
        """Yield games as JSON lines, or as PGN text separated by blank lines."""
        col, end = ("pgn", "\n\n") if fmt == "pgn" else ("data", "\n")
        sql, args = self._where(source, None)
        last = 0
        while True:  # batches by rowid, so big exports don't sit in memory or hold the lock
            with self.lock:
                rows = self.db.execute(
                    f"select rowid, {col} from games{sql} and rowid>? order by rowid limit 500", [*args, last]
                ).fetchall()
            if not rows:
                return
            for _, text in rows:
                yield text + end
            last = rows[-1][0]
