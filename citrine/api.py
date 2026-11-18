import os
from functools import lru_cache
from typing import Literal

import httpx
from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import PlainTextResponse, StreamingResponse

from .http import Client
from .models import Game, GamesIn, ProfileIn
from .sources import SourceError, chesscom, lichess, resolve, resolve_profile
from .store import Store
from .validate import parse_pgn

app = FastAPI(title="citrine", description="Open API for chess game data.", version="0.1.0")

PGN_TYPE = "application/x-chess-pgn"
SOURCES = {"lichess": lichess, "chesscom": chesscom}


@lru_cache
def get_store() -> Store:
    return Store(os.environ.get("CITRINE_DB", "citrine.db"))


@lru_cache
def get_client() -> Client:
    return Client()


def save(store, games, errors):
    return {"games": games, "new": sum(store.add(g) for g in games), "errors": errors}


def fetch(client, ref, max_games=50):
    """Run a source and return (pgns, errors), turning upstream failures into HTTP errors."""
    mod = SOURCES.get(ref.source)
    if not mod:
        raise HTTPException(501, f"{ref.source} source is not available")
    try:
        if ref.kind == "game":
            return mod.fetch_game(client, ref.value)
        return mod.fetch_profile(client, ref.value, max_games)
    except SourceError as e:
        raise HTTPException(e.status, e.message)
    except httpx.HTTPStatusError as e:
        code = e.response.status_code
        raise HTTPException(404 if code == 404 else 502, f"{ref.source} answered {code}")
    except httpx.HTTPError:
        raise HTTPException(502, f"could not reach {ref.source}")


def ingest(store, client, ref, max_games=50):
    pgns, errors = fetch(client, ref, max_games)
    games = []
    for p in pgns:
        gs, errs = parse_pgn(p, source=ref.source, source_id=ref.value if ref.kind == "game" else None)
        games += gs
        errors += errs
    return save(store, games, errors)


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/games")
def post_games(body: GamesIn, store: Store = Depends(get_store), client: Client = Depends(get_client)):
    if body.pgn:
        return save(store, *parse_pgn(body.pgn))
    try:
        ref = resolve(body.url)
    except SourceError as e:
        raise HTTPException(e.status, e.message)
    if ref.kind != "game":
        raise HTTPException(400, "that is a profile link, use POST /profiles")
    return ingest(store, client, ref)


@app.post("/profiles")
def post_profiles(body: ProfileIn, store: Store = Depends(get_store), client: Client = Depends(get_client)):
    try:
        ref = resolve(body.profile_url) if body.profile_url else resolve_profile(body.source, body.username)
    except SourceError as e:
        raise HTTPException(e.status, e.message)
    if ref.kind != "profile":
        raise HTTPException(400, "that is a game link, use POST /games")
    r = ingest(store, client, ref, body.max_games)
    return {"found": len(r["games"]), "new": r["new"], "errors": r["errors"]}


@app.get("/export")
def export(source: str | None = None, format: Literal["jsonl", "pgn"] = "jsonl", store: Store = Depends(get_store)):
    return StreamingResponse(store.export(source, format), media_type=PGN_TYPE if format == "pgn" else "application/x-ndjson")


@app.post("/judge/{game_id}", status_code=501)
def judge(game_id: str):
    return {"detail": "move judging is not built yet"}


@app.get("/games/{game_id}", response_model=Game)
def get_game(game_id: str, store: Store = Depends(get_store)):
    g = store.get(game_id)
    if not g:
        raise HTTPException(404, "game not found")
    return g


@app.get("/games/{game_id}/pgn", response_class=PlainTextResponse)
def get_pgn(game_id: str, store: Store = Depends(get_store)):
    return PlainTextResponse(get_game(game_id, store).pgn + "\n", media_type=PGN_TYPE)


@app.get("/games", response_model=list[Game])
def list_games(
    source: str | None = None,
    player: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    store: Store = Depends(get_store),
):
    return store.list(source, player, limit, offset)
