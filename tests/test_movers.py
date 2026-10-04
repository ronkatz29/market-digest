from market_digest.finnhub_client import Quote
from market_digest.movers import pick_movers


def q(ticker, pct):
    return Quote(ticker, 100.0, 100.0, pct, 0)


def test_picks_top_gainers_and_worst_losers():
    quotes = [q("A", 1), q("B", 9), q("C", -7), q("D", 4), q("E", -2), q("F", 6), q("G", -5), q("H", -0.5)]
    movers = pick_movers(quotes, n=3)
    assert [m.ticker for m in movers.gainers] == ["B", "F", "D"]
    assert [m.ticker for m in movers.losers] == ["C", "G", "E"]
    assert len(movers.all()) == 6


def test_all_up_day_has_no_losers():
    movers = pick_movers([q("A", 1), q("B", 2), q("C", 3), q("D", 4)], n=3)
    assert [m.ticker for m in movers.gainers] == ["D", "C", "B"]
    assert movers.losers == []


def test_small_universe_never_lists_a_stock_twice():
    movers = pick_movers([q("A", 2), q("B", -1)], n=3)
    assert [m.ticker for m in movers.gainers] == ["A"]
    assert [m.ticker for m in movers.losers] == ["B"]
