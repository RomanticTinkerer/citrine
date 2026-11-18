import pytest

from citrine.sources import Ref, SourceError, resolve


@pytest.mark.parametrize(
    "url,ref",
    [
        ("https://lichess.org/abcd1234", Ref("lichess", "game", "abcd1234")),
        ("https://lichess.org/abcd1234efgh/black?x=1", Ref("lichess", "game", "abcd1234")),
        ("https://lichess.org/@/Some_User", Ref("lichess", "profile", "Some_User")),
        ("https://www.chess.com/game/live/12345", Ref("chesscom", "game", "live/12345")),
        ("https://www.chess.com/analysis/game/daily/777?tab=review", Ref("chesscom", "game", "daily/777")),
        ("https://www.chess.com/live/game/99", Ref("chesscom", "game", "live/99")),
        ("https://www.chess.com/member/hikaru", Ref("chesscom", "profile", "hikaru")),
    ],
)
def test_known_links(url, ref):
    assert resolve(url) == ref


@pytest.mark.parametrize(
    "url",
    ["http://169.254.169.254/latest", "https://evil.test/https://lichess.org/abcd1234", "https://lichess.org.evil.test/abcd1234", "nonsense"],
)
def test_other_hosts_refused(url):
    with pytest.raises(SourceError):
        resolve(url)
