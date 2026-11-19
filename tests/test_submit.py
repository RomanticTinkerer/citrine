import httpx

from citrine import download
from citrine.http import Client

PGN = '[Event "Rated blitz game"]\n[White "Bob"]\n[Black "Ann"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n'


def test_submit_downloads_and_reports(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "Client", lambda cache: Client(cache, transport=httpx.MockTransport(lambda r: httpx.Response(200, text=PGN))))
    lines = download.submit(["https://lichess.org/@/bob", str(tmp_path), "2020", "2021", "5"])
    assert lines[0].startswith("lichess/bob: 1 games") and (tmp_path / "lichess_bob.pgn").exists()


def test_submit_explains_bad_forms(tmp_path):
    assert "use 2020" in download.submit(["lichess:bob", str(tmp_path), "soon", "", ""])[0]
    assert "unsupported link" in download.submit(["https://example.com/x", str(tmp_path), "", "", ""])[0]
    assert "Paste a link" in download.submit(["", str(tmp_path), "", "", ""])[0]
    assert "must be a number" in download.submit(["lichess:bob", str(tmp_path), "", "", "lots"])[0]
