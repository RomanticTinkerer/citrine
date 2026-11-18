import sqlite3
import threading

from .models import Game


class Store:
    def __init__(self, path):
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.lock = threading.Lock()  # ponytail: one connection plus a lock, fine until heavy concurrent writes
        self.db.execute(
            "create table if not exists games(id text primary key, source text, white text, black text, data text)"
        )

    def add(self, g: Game) -> bool:
        """Insert a game. Returns False if it was already stored."""
        with self.lock:
            cur = self.db.execute(
                "insert or ignore into games values (?,?,?,?,?)",
                (g.id, g.source, g.white.name.lower(), g.black.name.lower(), g.model_dump_json()),
            )
            self.db.commit()
            return cur.rowcount == 1

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
            sql += " and (white=? or black=?)"
            args += [player.lower()] * 2
        return sql, args

    def list(self, source=None, player=None, limit=50, offset=0):
        sql, args = self._where(source, player)
        with self.lock:
            rows = self.db.execute(
                f"select data from games{sql} order by rowid limit ? offset ?", [*args, limit, offset]
            ).fetchall()
        return [Game.model_validate_json(r[0]) for r in rows]

    def export(self, source=None):
        """Yield one JSON line per game."""
        sql, args = self._where(source, None)
        last = 0
        while True:  # batches by rowid, so big exports don't sit in memory or hold the lock
            with self.lock:
                rows = self.db.execute(
                    f"select rowid, data from games{sql} and rowid>? order by rowid limit 500", [*args, last]
                ).fetchall()
            if not rows:
                return
            for _, data in rows:
                yield data + "\n"
            last = rows[-1][0]
