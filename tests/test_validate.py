from citrine.validate import parse_pgn

GOOD = """[Event "t"]
[White "a"]
[Black "b"]
[WhiteElo "1500"]
[Result "1-0"]
[UTCDate "2024.01.02"]

1. e4 { [%clk 0:03:00] } e5 { [%clk 0:02:59] } 2. Nf3 Nc6 1-0
"""


def test_good_game():
    games, errors = parse_pgn(GOOD)
    assert not errors
    g = games[0]
    assert g.moves_uci == ["e2e4", "e7e5", "g1f3", "b8c6"]
    assert g.clocks == [180, 179, None, None]
    assert g.white.elo == 1500 and g.date == "2024-01-02"
    assert parse_pgn(GOOD)[0][0].id == g.id  # stable id


def test_illegal_move_rejected():
    games, errors = parse_pgn('[White "a"]\n\n1. e4 e5 2. Ke3 Ke6 3. Ke5 *')
    assert not games and errors


def test_variant_rejected():
    games, errors = parse_pgn('[Variant "Chess960"]\n\n1. e4 e5 *')
    assert not games and "variant" in errors[0]


def test_garbage():
    assert parse_pgn("")[1] == ["no games found"]
