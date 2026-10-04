from types import SimpleNamespace

from market_digest.analyst import Analysis
from market_digest.finnhub_client import Article, Quote
from market_digest.run import run, trading_day
from market_digest.store import Store
from market_digest.universe import Company

# 2026-10-02 20:00 UTC = 16:00 New York, the close.
CLOSE_TS = 1790971200
COMPANIES = [Company(t, f"{t} Inc", "Tech") for t in ("UP", "FLAT", "DOWN")]
CHANGES = {"UP": 8.0, "FLAT": 0.0, "DOWN": -6.0, "SPY": 0.5}


class FakeFinnhub:
    def __init__(self, prices=None, timestamp=CLOSE_TS):
        self.prices = prices or {}
        self.timestamp = timestamp
        self.quoted = []

    def quote(self, ticker):
        self.quoted.append(ticker)
        return Quote(ticker, self.prices.get(ticker, 100.0), 100.0, CHANGES[ticker], self.timestamp)

    def company_news(self, ticker, start, end):
        return [Article(f"{ticker} news", "s", "Reuters", f"https://example.com/{ticker}", 1)]


class FakeClaude:
    def __init__(self, fail_for=()):
        self.fail_for = fail_for
        self.messages = SimpleNamespace(parse=self._parse, create=self._create)

    def _parse(self, **kwargs):
        prompt = kwargs["messages"][0]["content"]
        ticker = prompt.split("Stock: ")[1].split(" ")[0]
        if ticker in self.fail_for:
            raise RuntimeError("boom")
        parsed = Analysis(
            headline="h", what_happened="w", why="y", no_clear_news=False,
            source_urls=[f"https://example.com/{ticker}"],
            concept={"name": "Concept", "lesson": "l"},
            prediction={"call": "outperform", "confidence": "low", "reasoning": "r"},
        )
        return SimpleNamespace(parsed_output=parsed, stop_reason="end_turn")

    def _create(self, **kwargs):
        return SimpleNamespace(content=[SimpleNamespace(type="text", text="Looking back...")])


def test_trading_day_uses_new_york_date():
    assert trading_day(Quote("SPY", 1, 1, 0, CLOSE_TS)) == "2026-10-02"
    # 01:00 UTC on the 3rd is still the evening of the 2nd in New York.
    assert trading_day(Quote("SPY", 1, 1, 0, CLOSE_TS + 5 * 3600)) == "2026-10-02"


def test_run_writes_digest_and_opens_predictions(tmp_path):
    store = Store(tmp_path)
    digest = run(FakeFinnhub(), FakeClaude(), store, COMPANIES)

    assert digest["date"] == "2026-10-02"
    assert digest["benchmark"] == {"ticker": "SPY", "close": 100.0, "change_pct": 0.5}
    assert [m["ticker"] for m in digest["movers"]] == ["UP", "DOWN"]
    assert digest["movers"][0]["sources"] == [
        {"headline": "UP news", "source": "Reuters", "url": "https://example.com/UP"}
    ]
    assert "source_urls" not in digest["movers"][0]
    assert digest["market"]["scanned"] == 3
    assert (digest["market"]["advancers"], digest["market"]["decliners"]) == (1, 1)
    assert [s["ticker"] for s in digest["market"]["stocks"]] == ["UP", "FLAT", "DOWN"]
    assert store.load_digest("2026-10-02") == digest
    assert [p["id"] for p in store.load_predictions()] == ["2026-10-02:UP", "2026-10-02:DOWN"]


def test_run_analyses_five_movers_each_way(tmp_path, monkeypatch):
    changes = {f"G{i}": float(i) for i in range(1, 8)} | {f"L{i}": -float(i) for i in range(1, 8)}
    for ticker, change in changes.items():
        monkeypatch.setitem(CHANGES, ticker, change)
    companies = [Company(t, f"{t} Inc", "Tech") for t in changes]

    digest = run(FakeFinnhub(), FakeClaude(), Store(tmp_path), companies)

    assert [m["ticker"] for m in digest["movers"]] == [
        "G7", "G6", "G5", "G4", "G3", "L7", "L6", "L5", "L4", "L3",
    ]
    assert digest["market"]["scanned"] == 14


def test_run_is_a_no_op_when_the_day_is_already_digested(tmp_path):
    store = Store(tmp_path)
    run(FakeFinnhub(), FakeClaude(), store, COMPANIES)
    finnhub = FakeFinnhub()
    assert run(finnhub, FakeClaude(), store, COMPANIES) is None
    assert finnhub.quoted == ["SPY"]
    assert len(store.load_predictions()) == 2


def test_force_rebuilds_without_duplicating_predictions(tmp_path):
    store = Store(tmp_path)
    run(FakeFinnhub(), FakeClaude(), store, COMPANIES)
    assert run(FakeFinnhub(), FakeClaude(), store, COMPANIES, force=True) is not None
    assert len(store.load_predictions()) == 2


def test_one_failing_stock_does_not_lose_the_digest(tmp_path):
    store = Store(tmp_path)
    digest = run(FakeFinnhub(), FakeClaude(fail_for=("UP",)), store, COMPANIES)
    assert [m["ticker"] for m in digest["movers"]] == ["DOWN"]


def test_due_predictions_are_scored_with_a_retrospective(tmp_path):
    store = Store(tmp_path)
    for day in ("2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01"):
        store.save_digest(day, {"date": day, "movers": []})
    store.save_predictions([{
        "id": "2026-09-25:FLAT", "ticker": "FLAT", "name": "FLAT Inc", "made_on": "2026-09-25",
        "entry_close": 100.0, "benchmark_entry_close": 100.0, "call": "outperform",
        "confidence": "low", "reasoning": "r", "concept": "c", "status": "open",
    }])

    digest = run(FakeFinnhub(prices={"FLAT": 105.0}), FakeClaude(), store, COMPANIES)

    assert digest["resolved"] == ["2026-09-25:FLAT"]
    scored = store.load_predictions()[0]
    assert scored["status"] == "resolved" and scored["hit"] is True
    assert scored["excess_return_pct"] == 5.0
    assert scored["retrospective"] == "Looking back..."
