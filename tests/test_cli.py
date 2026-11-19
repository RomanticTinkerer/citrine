import httpx
import pytest

from citrine import cli, download
from citrine.http import Client

PGN = '[Event "Rated blitz game"]\n[White "Bob"]\n[Black "Ann"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n'


def fake_client(handler):
    return lambda cache: Client(cache, transport=httpx.MockTransport(handler))


def test_prompts_then_saves_files(tmp_path, monkeypatch):
    monkeypatch.setattr(download, "Client", fake_client(lambda req: httpx.Response(200, text=PGN)))
    answers = iter(["bob", ""])  # lichess bob, skip chess.com
    monkeypatch.setattr("builtins.input", lambda _: next(answers))
    out = tmp_path / "CitrineData"
    with pytest.raises(SystemExit) as e:
        cli.main(["--out", str(out)])
    assert e.value.code == 0
    assert "1. e4 e5" in (out / "lichess_bob.pgn").read_text()
    assert (out / "lichess_bob.jsonl").read_text().count("\n") == 1 and (out / "citrine.db").exists()
    assert not (out / "chesscom_.pgn").exists()


def test_upstream_failure_is_reported(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(download, "Client", fake_client(lambda req: httpx.Response(404)))
    with pytest.raises(SystemExit) as e:
        cli.main(["--lichess", "nobody", "--out", str(tmp_path)])
    assert e.value.code == 1 and "failed" in capsys.readouterr().out


def test_link_and_range_flags(tmp_path, monkeypatch):
    seen = {}

    def handler(req):
        seen.update(req.url.params)
        return httpx.Response(200, text=PGN)

    monkeypatch.setattr(download, "Client", fake_client(handler))
    with pytest.raises(SystemExit) as e:
        cli.main(["https://lichess.org/@/bob", "--from", "2020", "--to", "2020-02", "--out", str(tmp_path)])
    assert e.value.code == 0 and seen["since"] == "1577836800000" and seen["until"] == "1583020799999"
    assert (tmp_path / "lichess_bob.pgn").exists()


def test_bad_date_exits_with_a_hint(tmp_path):
    with pytest.raises(SystemExit) as e:
        cli.main(["lichess:bob", "--from", "last week"])
    assert "use 2020, 2020-05 or 2020-05-17" in str(e.value)
