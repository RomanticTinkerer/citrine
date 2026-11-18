import httpx
import pytest

from citrine import cli
from citrine.http import Client

PGN = '[Event "Rated blitz game"]\n[White "Bob"]\n[Black "Ann"]\n[Result "1-0"]\n\n1. e4 e5 1-0\n'


def fake_client(handler):
    return lambda cache: Client(cache, transport=httpx.MockTransport(handler))


def test_prompts_then_saves_files(tmp_path, monkeypatch):
    monkeypatch.setattr(cli, "Client", fake_client(lambda req: httpx.Response(200, text=PGN)))
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
    monkeypatch.setattr(cli, "Client", fake_client(lambda req: httpx.Response(404)))
    with pytest.raises(SystemExit) as e:
        cli.main(["--lichess", "nobody", "--out", str(tmp_path)])
    assert e.value.code == 1 and "failed" in capsys.readouterr().out
