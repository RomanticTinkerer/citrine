# citrine

An open API for chess game data. Give it PGN text or a game link, and it gives you back clean, validated JSON game records. Records are stored in SQLite and can be exported as JSONL for training.

It needs no API keys and no accounts. License: AGPL-3.0-only.

## Run it

```
uv sync
uv run uvicorn citrine.api:app
```

Interactive docs and the full schema are at `http://localhost:8000/docs`.

## Endpoints

- `POST /games` with `{"pgn": "..."}` or `{"url": "..."}`. A PGN can hold many games. Returns `{games, new, errors}`. Games that fail validation show up in `errors` and are not stored.
- `POST /profiles` with `{"profile_url": "..."}` or `{"source": "lichess", "username": "..."}`, plus optional `max_games` (default 50, max 500). Returns `{found, new, errors}`.
- `GET /games/{id}` and `GET /games?source=&player=&limit=&offset=`
- `GET /export?source=` streams one game per line (`application/x-ndjson`).
- `POST /judge/{id}` returns 501 for now. Move evaluation comes later.
- `GET /health`

A game's `id` is a hash of the players, date and moves, so the same game from two places is stored once.

## Sources

- **PGN text**: always works, needs no network.
- **Lichess** (game and profile links): uses the official, open Lichess API.
- **Chess.com** (live game and profile links): off by default. It reads the same JSON the chess.com website uses. That is undocumented, may break any day, and may be against their terms. Turn it on yourself with `CITRINE_ENABLE_CHESSCOM=1` and check their rules first. Daily games are not supported yet. A profile with many games is slow, because it makes one request per game.

Only standard chess is accepted. Variants, Chess960 and custom start positions are rejected, and every game is replayed move by move to check it is legal.

Links are matched against known patterns and the request URL is built by citrine, so the API can't be pointed at other hosts.

## Settings

All environment variables:

- `CITRINE_DB`: SQLite file, default `citrine.db`
- `CITRINE_CACHE`: folder for cached upstream responses, default `.cache`
- `CITRINE_CONTACT`: your email or URL, sent in the User-Agent so sites can reach you
- `CITRINE_ENABLE_CHESSCOM`: set to `1` to enable the chess.com source

Requests to other sites are spaced one second apart, retried after a 429, and cached on disk.

## Tests

```
uv run pytest
```

Tests use saved responses and never touch the network.
