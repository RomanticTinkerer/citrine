import json
import sqlite3

from citrine.store import Store
from citrine.validate import parse_pgn

PGN = '[White "Ann"]\n[Black "Bob"]\n[Result "1-0"]\n\n1. e4 e5 2. Nf3 1-0\n'


def test_dedup_list_export():
    s = Store(":memory:")
    g = parse_pgn(PGN)[0][0]
    assert s.add(g) and not s.add(g)
    assert s.get(g.id).moves_uci == ["e2e4", "e7e5", "g1f3"]
    assert len(s.list(player="ANN")) == 1 and s.list(player="nobody") == []
    assert s.list(source="lichess") == []
    lines = list(s.export())
    assert len(lines) == 1 and json.loads(lines[0])["id"] == g.id
    assert "[White \"Ann\"]" in next(s.export(fmt="pgn"))


def test_sql_table_is_readable():
    s = Store(":memory:")
    s.add(parse_pgn(PGN)[0][0])
    row = s.db.execute("select white, black, result, moves, pgn from games").fetchone()
    assert row[:4] == ("Ann", "Bob", "1-0", "1. e4 e5 2. Nf3") and row[4].startswith("[")


def test_old_database_is_upgraded(tmp_path):
    g = parse_pgn(PGN)[0][0]
    old = json.loads(g.model_dump_json())
    del old["moves_san"]  # records from before moves_san existed
    path = tmp_path / "old.db"
    db = sqlite3.connect(path)
    db.execute("create table games(id text primary key, source text, white text, black text, data text)")
    db.execute("insert into games values (?,?,?,?,?)", (g.id, "pgn", "ann", "bob", json.dumps(old)))
    db.commit()
    db.close()
    s = Store(path)
    assert s.db.execute("select white, moves, pgn is not null from games").fetchone() == ("Ann", "1. e4 e5 2. Nf3", 1)
    assert s.get(g.id).moves_san == ["e4", "e5", "Nf3"]
