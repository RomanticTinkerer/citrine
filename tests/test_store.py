import json

from citrine.store import Store
from citrine.validate import parse_pgn

PGN = '[White "Ann"]\n[Black "Bob"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n'


def test_dedup_list_export():
    s = Store(":memory:")
    g = parse_pgn(PGN)[0][0]
    assert s.add(g) and not s.add(g)
    assert s.get(g.id).moves_uci == ["e2e4", "e7e5"]
    assert len(s.list(player="ANN")) == 1 and s.list(player="nobody") == []
    assert s.list(source="lichess") == []
    lines = list(s.export())
    assert len(lines) == 1 and json.loads(lines[0])["id"] == g.id
