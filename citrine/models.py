from pydantic import BaseModel, Field, model_validator


class Player(BaseModel):
    name: str
    elo: int | None = None


class Game(BaseModel):
    id: str  # sha1 of players, date and moves, so the same game dedups across sources
    source: str  # pgn | lichess | chesscom
    source_url: str | None = None
    source_id: str | None = None
    white: Player
    black: Player
    result: str
    termination: str | None = None
    time_control: str | None = None
    rated: bool | None = None
    date: str | None = None
    eco: str | None = None
    opening: str | None = None
    moves_uci: list[str]
    moves_san: list[str] = []  # same moves as readable notation, e.g. Nf3
    clocks: list[float | None]  # seconds left after each move, null when unknown
    pgn: str
    fetched_at: str
    labels: dict | None = None  # filled in later by the judge


class GamesIn(BaseModel):
    url: str | None = None
    pgn: str | None = Field(None, max_length=5_000_000)

    @model_validator(mode="after")
    def _one_of(self):
        if bool(self.url) == bool(self.pgn):
            raise ValueError("send exactly one of url or pgn")
        return self


class ProfileIn(BaseModel):
    profile_url: str | None = None
    source: str | None = None
    username: str | None = None
    max_games: int = Field(50, ge=1, le=500)

    @model_validator(mode="after")
    def _one_of(self):
        if bool(self.profile_url) == bool(self.source and self.username):
            raise ValueError("send profile_url, or source and username")
        return self
