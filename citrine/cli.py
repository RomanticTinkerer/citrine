import argparse
import sys

from . import period
from .download import ALL, parse_target, run
from .sources import SourceError, resolve_profile


def main(argv=None):
    ap = argparse.ArgumentParser(
        prog="citrine",
        description="Download games from Lichess and Chess.com (live and daily) into a folder as PGN and JSONL.",
        epilog="examples:\n  citrine https://lichess.org/@/DrNykterstein\n  citrine chesscom:hikaru --from 2020 --to 2021-06\n  citrine --lichess bob --chesscom ann --out ~/chess --max 500",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("targets", nargs="*", metavar="LINK_OR_NAME", help="a game or profile link, or lichess:name / chesscom:name")
    ap.add_argument("--lichess", metavar="USER")
    ap.add_argument("--chesscom", metavar="USER")
    ap.add_argument("--out", default="CitrineData", help="folder to save into (default: CitrineData)")
    ap.add_argument("--from", dest="since", metavar="DATE", help="first day: 2020, 2020-05 or 2020-05-17")
    ap.add_argument("--to", dest="until", metavar="DATE", help="last day, same formats (a bare year means its last day)")
    ap.add_argument("--max", type=int, default=ALL, help="stop after this many games per account (newest first)")
    ap.add_argument("--tui", action="store_true", help="open the terminal form instead")
    ap.add_argument("--serve", action="store_true", help="run the web API on http://127.0.0.1:8000")
    a = ap.parse_args(argv)
    if a.serve:
        import uvicorn

        from .api import app  # the object, not a "module:name" string, so a frozen binary can find it

        return uvicorn.run(app, host="127.0.0.1", port=8000)
    if a.tui:
        from .tui import main as tui

        return tui(a.out)
    try:
        since, until = period.parse_range(a.since, a.until)
        refs = [parse_target(t) for t in a.targets]
        refs += [resolve_profile(s, n) for s, n in (("lichess", a.lichess), ("chesscom", a.chesscom)) if n]
        if not refs:  # nothing given: ask
            for s in ("lichess", "chesscom"):
                if name := input(f"{s} username (Enter to skip): ").strip():
                    refs.append(resolve_profile(s, name))
    except (ValueError, SourceError) as e:
        sys.exit(f"citrine: {getattr(e, 'message', e)}")
    if not refs:
        sys.exit("No usernames or links given.")
    failed = False
    for ref in refs:
        print(f"{ref.source}/{ref.value}: fetching, this can take a few minutes...", flush=True)
        shown = lambda done, total: print(f"\r  {done}/{total} games", end="", file=sys.stderr, flush=True) if sys.stderr.isatty() else None
        r = run(ref, a.out, since, until, a.max, shown)
        if sys.stderr.isatty():
            print(file=sys.stderr)
        if r["failed"]:
            print(f"{r['label']}: failed: {r['failed']}")
            failed = True
            continue
        print(f"{r['label']}: {r['games']} games ({r['new']} new) saved to {r['files'][0]}")
        for e in r["errors"][:5]:
            print("  skipped:", e)
    sys.exit(1 if failed else 0)
