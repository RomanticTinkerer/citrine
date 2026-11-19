# citrine

An open API for chess game data. Give it PGN text or a game link, and it gives you back clean, validated JSON game records. Records are stored in SQLite and can be exported as JSONL or PGN.

It needs no API keys and no accounts. License: AGPL-3.0-only.

## Install (Linux)

```
curl -fsSL https://raw.githubusercontent.com/RomanticTinkerer/citrine/main/install.sh | sudo sh
```

It puts a private Python environment in `/opt/citrine` and links `citrine` and `citrine-gui` into `/usr/local/bin`. It needs Python 3.11 or newer. To remove it:

```
curl -fsSL https://raw.githubusercontent.com/RomanticTinkerer/citrine/main/install.sh | sudo sh -s -- --uninstall
```

Your downloaded games are not touched. The window needs GTK4 and libadwaita from your distro (the installer prints the command if they are missing). The command line and terminal form work without them.

## Prebuilt binary (x86_64 Linux)

Each [release](https://github.com/RomanticTinkerer/citrine/releases/latest) has a single `citrine-linux-x86_64` file. No Python needed:

```
curl -fLO https://github.com/RomanticTinkerer/citrine/releases/latest/download/citrine-linux-x86_64
chmod +x citrine-linux-x86_64
./citrine-linux-x86_64 lichess:bob --from 2023
```

It does the command line, `--tui` and `--serve`. It does not include the GTK window, which needs your system's GTK4 libraries (use the installer for that). Check the download against `SHA256SUMS` from the same release. Rebuild it yourself with `uv run --with pyinstaller pyinstaller --onefile --name citrine-linux-x86_64 --collect-submodules uvicorn --hidden-import citrine.api --exclude-module gi launcher.py`.

## Download games

Three ways, same result: a folder with a `.pgn` and a `.jsonl` file per account (like `lichess_name.pgn`), plus `citrine.db`.

**Command line**

```
citrine https://lichess.org/@/DrNykterstein
citrine chesscom:hikaru --from 2020 --to 2021-06 --out ~/chess
citrine lichess:bob chesscom:ann --max 500
```

Give it profile or game links, or `lichess:name` / `chesscom:name`. With no arguments it asks for usernames. Chess.com live games and old daily (correspondence) games are both downloaded.

- `--from` and `--to` set a date range. Write a year (`2020`), a month (`2020-05`) or a day (`2020-05-17`). `--from 2019 --to 2021` covers all of 2019, 2020 and 2021. Either one can be left out.
- `--max N` stops after N games per account, newest first.
- `--out FOLDER` picks the folder (default `CitrineData`).

**Terminal form:** `citrine --tui` shows a form: paste a link, pick the folder, set the range, press Enter on Download.

**Window:** `citrine-gui` opens a GTK4 and libadwaita window with the same boxes: paste a link, choose a folder, press Download.

**From a checkout instead of the installer:** `uv sync`, then `uv run citrine ...`. The window needs the system PyGObject, so run it with `python3 -m citrine.window` from a virtualenv made with `--system-site-packages`.

## Run the API

```
citrine --serve
```

or `uv run uvicorn citrine.api:app`. Interactive docs and the full schema are at `http://localhost:8000/docs`.

## Endpoints

- `POST /games` with `{"pgn": "..."}` or `{"url": "..."}`. A PGN can hold many games. Returns `{games, new, errors}`. Games that fail validation show up in `errors` and are not stored.
- `POST /profiles` with `{"profile_url": "..."}` or `{"source": "lichess", "username": "..."}`, plus optional `max_games` (default 50, max 500) and `since` / `until` (`2020`, `2020-05` or `2020-05-17`). Returns `{found, new, errors}`.
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
- **Chess.com** (live and daily game links, profile links): off by default. It reads the same JSON the chess.com website uses. That is undocumented, may break any day, and may be against their terms. Turn it on yourself with `CITRINE_ENABLE_CHESSCOM=1` and check their rules first. Old games are included: the profile list goes back to the first game, and a date range reads only the games near its edges to find where to start. A profile makes one request per game, four at a time, so a few hundred games take a couple of minutes. If chess.com stops answering, the games fetched so far are still saved and the rest are reported in `errors`.

Only standard chess is accepted. Variants, Chess960 and custom start positions are rejected, and every game is replayed move by move to check it is legal.

Links are matched against known patterns and the request URL is built by citrine, so the API can't be pointed at other hosts.

## Settings

All environment variables:

- `CITRINE_DB`: SQLite file, default `citrine.db`
- `CITRINE_CACHE`: folder for cached upstream responses, default `.cache`
- `CITRINE_CONTACT`: your email or URL, sent in the User-Agent so sites can reach you
- `CITRINE_ENABLE_CHESSCOM`: set to `1` to enable the chess.com source in the API (the command line, terminal form and window turn it on when you ask for Chess.com)

Requests to other sites are retried after a 429 (waiting as long as the site asks) and cached on disk.

## Tests

```
uv run pytest
```

Tests use saved responses and never touch the network.
