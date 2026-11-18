"""Sources turn a link or username into PGN text. We never fetch a URL the caller gives us:
the link is matched against known patterns and the request URL is built here."""

import re
from typing import NamedTuple


class SourceError(Exception):
    def __init__(self, status, message):
        super().__init__(message)
        self.status, self.message = status, message


class Ref(NamedTuple):
    source: str  # lichess | chesscom
    kind: str  # game | profile
    value: str  # game id (chesscom: "live/123") or username


_Q = r"/?(?:[?#].*)?"
_PATTERNS = [
    ("lichess", "game", r"https?://(?:www\.)?lichess\.org/(?:game/export/)?([A-Za-z0-9]{8})(?:[A-Za-z0-9]{4})?(?:/(?:white|black))?" + _Q),
    ("lichess", "profile", r"https?://(?:www\.)?lichess\.org/@/([A-Za-z0-9_-]{2,30})" + _Q),
    ("chesscom", "game", r"https?://(?:www\.)?chess\.com/(?:analysis/)?(?:game/(live|daily)|(live|daily)/game)/(\d+)" + _Q),
    ("chesscom", "profile", r"https?://(?:www\.)?chess\.com/member/([A-Za-z0-9_-]{3,25})" + _Q),
]


def resolve(url: str) -> Ref:
    for source, kind, pat in _PATTERNS:
        if m := re.fullmatch(pat, url.strip()):
            g = [x for x in m.groups() if x]
            return Ref(source, kind, "/".join(g))
    raise SourceError(400, "unsupported link: use a lichess.org or chess.com game or profile link")


def resolve_profile(source: str, username: str) -> Ref:
    if source not in ("lichess", "chesscom") or not re.fullmatch(r"[A-Za-z0-9_-]{2,30}", username):
        raise SourceError(400, "unknown source or bad username")
    return Ref(source, "profile", username)
