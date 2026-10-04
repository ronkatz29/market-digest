from market_digest.finnhub_client import Quote
from market_digest.market import summarize
from market_digest.universe import Company


def q(ticker, pct, price=100.0):
    return Quote(ticker, price, 100.0, pct, 0)


COMPANIES = {
    "A": Company("A", "A Inc", "Tech"),
    "B": Company("B", "B Inc", "Tech"),
    "C": Company("C", "C Inc", "Energy"),
    "D": Company("D", "D Inc", "Energy"),
    "E": Company("E", "E Inc", "Health"),
}


def test_counts_breadth_and_median():
    market = summarize([q("A", 4), q("B", 1), q("C", -3), q("D", 0), q("E", 2)], COMPANIES)
    assert market["scanned"] == 5
    assert (market["advancers"], market["decliners"], market["unchanged"]) == (3, 1, 1)
    assert market["median_change_pct"] == 1


def test_sectors_are_equal_weighted_and_sorted_best_first():
    market = summarize([q("A", 4), q("B", 1), q("C", -3), q("D", 0), q("E", 2)], COMPANIES)
    assert market["sectors"] == [
        {"sector": "Tech", "change_pct": 2.5, "advancers": 2, "decliners": 0, "count": 2},
        {"sector": "Health", "change_pct": 2.0, "advancers": 1, "decliners": 0, "count": 1},
        {"sector": "Energy", "change_pct": -1.5, "advancers": 0, "decliners": 1, "count": 2},
    ]


def test_lists_every_stock_with_rounded_change():
    market = summarize([q("A", 1.23456, price=12.5)], COMPANIES)
    assert market["stocks"] == [
        {"ticker": "A", "name": "A Inc", "sector": "Tech", "close": 12.5, "change_pct": 1.23}
    ]


def test_skips_quotes_outside_the_universe():
    market = summarize([q("A", 1), q("ZZZ", 9)], COMPANIES)
    assert market["scanned"] == 1
    assert [s["ticker"] for s in market["stocks"]] == ["A"]


def test_no_quotes_gives_an_empty_market():
    market = summarize([], COMPANIES)
    assert market["scanned"] == 0
    assert market["median_change_pct"] == 0
    assert market["sectors"] == []
