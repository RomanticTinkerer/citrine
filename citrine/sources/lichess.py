BASE = "https://lichess.org"
PGN = "application/x-chess-pgn"
OPTS = {"clocks": "true", "opening": "true"}
MONTH = 30 * 86400


def fetch_game(client, game_id):
    return [client.get(f"{BASE}/game/export/{game_id}", accept=PGN, params=OPTS, ttl=MONTH)], []


def fetch_profile(client, username, max_games):
    text = client.get(f"{BASE}/api/games/user/{username}", accept=PGN, params={**OPTS, "max": max_games}, ttl=300)
    return [text], []
