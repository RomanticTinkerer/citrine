import os
from functools import lru_cache

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import StreamingResponse

from .models import Game, GamesIn
from .store import Store
from .validate import parse_pgn

app = FastAPI(title="citrine", description="Open API for chess game data.", version="0.1.0")


@lru_cache
def get_store() -> Store:
    return Store(os.environ.get("CITRINE_DB", "citrine.db"))


@app.get("/health")
def health():
    return {"ok": True}


@app.post("/games")
def post_games(body: GamesIn, store: Store = Depends(get_store)):
    if body.url:
        raise HTTPException(501, "url sources are not enabled yet")
    games, errors = parse_pgn(body.pgn)
    new = sum(store.add(g) for g in games)
    return {"games": games, "new": new, "errors": errors}


@app.get("/games/{game_id}", response_model=Game)
def get_game(game_id: str, store: Store = Depends(get_store)):
    g = store.get(game_id)
    if not g:
        raise HTTPException(404, "game not found")
    return g


@app.get("/games", response_model=list[Game])
def list_games(
    source: str | None = None,
    player: str | None = None,
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    store: Store = Depends(get_store),
):
    return store.list(source, player, limit, offset)
