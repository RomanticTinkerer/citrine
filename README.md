# citrine

An open API for chess game data. Give it PGN text or a game link, and it gives you back clean, validated JSON game records. Records are stored in SQLite and can be exported as JSONL or PGN.

It needs no API keys and no accounts. License: AGPL-3.0-only.

## Run it

```
uv sync
uv run uvicorn citrine.api:app
```

Interactive docs and the full schema are at `http://localhost:8000/docs`.

## Command line

```
uv run citrine
```

It asks for a Lichess and a Chess.com username (press Enter to skip one), fetches all their games, and saves them in a `CitrineData` folder: `citrine.db`, plus a `.pgn` and a `.jsonl` file per account, like `lichess_name.pgn`. Typing a Chess.com username counts as turning that source on (see the warning below).

Options: `--lichess USER` and `--chesscom USER` skip the questions, `--out FOLDER` changes the folder, `--max N` stops after N games per account.

## Endpoints

- `POST /games` with `{"pgn": "..."}` or `{"url": "..."}`. A PGN can hold many games. Returns `{games, new, errors}`. Games that fail validation show up in `errors` and are not stored.
- `POST /profiles` with `{"profile_url": "..."}` or `{"source": "lichess", "username": "..."}`, plus optional `max_games` (default 50, max 500). Returns `{found, new, errors}`.
- `GET /games/{id}` and `GET /games?source=&player=&limit=&offset=`. Each game has `moves_uci` and `moves_san` (readable, like `Nf3`).
- `GET /games/{id}/pgn` returns the game as PGN text, with clock comments when the source had clocks.
- `GET /export?source=&format=jsonl|pgn` streams every game, either one JSON record per line or one PGN file with all games.
- `POST /judge/{id}` returns 501 for now. Move evaluation comes later.
- `GET /health`

In the SQLite file, the `games` table has readable `white`, `black`, `result`, `date`, `moves` and `pgn` columns, plus `data` with the full JSON record. Older databases are upgraded automatically on startup.

A game's `id` is a hash of the players, date and moves, so the same game from two places is stored once.

## Sources

- **PGN text**: always works, needs no network.
- **Lichess** (game and profile links): uses the official, open Lichess API.
- **Chess.com** (live game and profile links): off by default. It reads the same JSON the chess.com website uses. That is undocumented, may break any day, and may be against their terms. Turn it on yourself with `CITRINE_ENABLE_CHESSCOM=1` and check their rules first. Daily games are not supported yet. A profile makes one request per game, four at a time, so a few hundred games take a couple of minutes. If chess.com stops answering, the games fetched so far are still saved and the rest are reported in `errors`.

Only standard chess is accepted. Variants, Chess960 and custom start positions are rejected, and every game is replayed move by move to check it is legal.

Links are matched against known patterns and the request URL is built by citrine, so the API can't be pointed at other hosts.

## Settings

All environment variables:

- `CITRINE_DB`: SQLite file, default `citrine.db`
- `CITRINE_CACHE`: folder for cached upstream responses, default `.cache`
- `CITRINE_CONTACT`: your email or URL, sent in the User-Agent so sites can reach you
- `CITRINE_ENABLE_CHESSCOM`: set to `1` to enable the chess.com source

Requests to other sites are retried after a 429 (waiting as long as the site asks) and cached on disk.

## Tests

```
uv run pytest
```

Tests use saved responses and never touch the network.
