from ..period import to_ms

BASE = "https://lichess.org"
PGN = "application/x-chess-pgn"
OPTS = {"clocks": "true", "opening": "true"}
MONTH = 30 * 86400


def fetch_game(client, game_id):
    return [client.get(f"{BASE}/game/export/{game_id}", accept=PGN, params=OPTS, ttl=MONTH)], []


def fetch_profile(client, username, max_games, since=None, until=None, progress=None):
    params = {**OPTS, "max": max_games}
    if since:
        params["since"] = to_ms(since)
    if until:
        params["until"] = to_ms(until, end=True)
    text = client.get(f"{BASE}/api/games/user/{username}", accept=PGN, params=params, ttl=300)
    return [text], []
