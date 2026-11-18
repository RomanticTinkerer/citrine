import argparse
import os
import sys
from pathlib import Path

from fastapi import HTTPException

from .api import ingest
from .http import Client
from .sources import SourceError, resolve_profile
from .store import Store

ALL = 10**9


def main(argv=None):
    ap = argparse.ArgumentParser(prog="citrine", description="Scrape all games for a Lichess and/or Chess.com username.")
    ap.add_argument("--lichess", metavar="USER")
    ap.add_argument("--chesscom", metavar="USER")
    ap.add_argument("--out", default="CitrineData", help="folder to save into (default: CitrineData)")
    ap.add_argument("--max", type=int, default=ALL, help="stop after this many games per account")
    a = ap.parse_args(argv)
    if not (a.lichess or a.chesscom):  # no flags: ask
        a.lichess = input("Lichess username (Enter to skip): ").strip()
        a.chesscom = input("Chess.com username (Enter to skip): ").strip()
    accounts = [(s, n) for s, n in (("lichess", a.lichess), ("chesscom", a.chesscom)) if n]
    if not accounts:
        sys.exit("No usernames given.")
    os.environ["CITRINE_ENABLE_CHESSCOM"] = "1"  # typing a chess.com username is the opt-in
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    store, client = Store(out / "citrine.db"), Client(out / ".cache")
    failed = False
    for source, name in accounts:
        print(f"{source}/{name}: fetching, this can take a few minutes...", flush=True)
        try:
            r = ingest(store, client, resolve_profile(source, name), a.max)
        except (SourceError, HTTPException) as e:
            print(f"{source}/{name}: failed: {getattr(e, 'message', None) or e.detail}")
            failed = True
            continue
        for fmt in ("pgn", "jsonl"):
            (out / f"{source}_{name}.{fmt}").write_text("".join(store.export(source, fmt, name)))
        print(f"{source}/{name}: {len(r['games'])} games ({r['new']} new) saved to {out / f'{source}_{name}.pgn'}")
        for e in r["errors"][:5]:
            print("  skipped:", e)
    sys.exit(1 if failed else 0)
