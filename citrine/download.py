"""One download, shared by the CLI, the TUI and the GTK window: a link or username in,
PGN and JSONL files in a folder out."""
import os
import re
from pathlib import Path

from fastapi import HTTPException

from . import period
from .api import ingest
from .http import Client
from .sources import Ref, SourceError, resolve, resolve_profile
from .store import Store

ALL = 10**9


def parse_target(text):
    """A Lichess or Chess.com link, or 'lichess:name' / 'chesscom:name'."""
    text = text.strip()
    if m := re.fullmatch(r"(lichess|chesscom|chess\.com)\s*[:/]\s*(\S+)", text, re.I):
        return resolve_profile("chesscom" if m[1].lower().startswith("chess") else "lichess", m[2])
    return resolve(text)


def run(ref: Ref, out, since=None, until=None, max_games=ALL, progress=None):
    """Download one link or profile into `out`. Never raises for site problems: see result['failed']."""
    os.environ["CITRINE_ENABLE_CHESSCOM"] = "1"  # asking for a chess.com link or name is the opt-in
    out = Path(out).expanduser()
    out.mkdir(parents=True, exist_ok=True)
    store, client = Store(out / "citrine.db"), Client(out / ".cache")
    result = {"label": f"{ref.source}/{ref.value}", "files": [], "games": 0, "new": 0, "errors": [], "failed": None}
    try:
        r = ingest(store, client, ref, max_games, since, until, progress)
    except (SourceError, HTTPException) as e:
        result["failed"] = getattr(e, "message", None) or e.detail
        return result
    name = ref.value.replace("/", "_")
    if ref.kind == "profile":
        text = {fmt: "".join(store.export(ref.source, fmt, ref.value)) for fmt in ("pgn", "jsonl")}
    else:  # one game: just that game
        text = {"pgn": "".join(g.pgn + "\n\n" for g in r["games"]), "jsonl": "".join(g.model_dump_json() + "\n" for g in r["games"])}
    for fmt, body in text.items():
        f = out / f"{ref.source}_{name}.{fmt}"
        f.write_text(body)
        result["files"].append(f)
    result.update(games=len(r["games"]), new=r["new"], errors=r["errors"])
    return result


def submit(values, progress=None):
    """Validate the form and download. Returns the lines to show; never raises."""
    target, folder, since, until, mx = (v.strip() for v in values)
    try:
        refs = [parse_target(t) for t in re.split(r"[\s,]+", target) if t]
        a, b = period.parse_range(since or None, until or None)
    except (ValueError, SourceError) as e:
        return [f"Check the form: {getattr(e, 'message', e)}"]
    if mx and not mx.isdigit():
        return ["Max games must be a number."]
    limit = int(mx) if mx else ALL
    if not refs:
        return ["Paste a link or type lichess:name or chesscom:name first."]
    lines = []
    for ref in refs:
        r = run(ref, folder or "CitrineData", a, b, limit, progress)
        if r["failed"]:
            lines.append(f"{r['label']}: failed: {r['failed']}")
        else:
            lines.append(f"{r['label']}: {r['games']} games ({r['new']} new) -> {r['files'][0]}")
            lines += [f"  skipped: {e}" for e in r["errors"][:3]]
    return lines
