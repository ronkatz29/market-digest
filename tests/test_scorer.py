from market_digest.analyst import Analysis
from market_digest.finnhub_client import Quote
from market_digest.scorer import due, new_prediction, resolve
from market_digest.universe import Company

DAYS = ["2026-09-25", "2026-09-28", "2026-09-29", "2026-09-30", "2026-10-01", "2026-10-02"]


def prediction(made_on="2026-09-25", call="underperform", status="open"):
    return {
        "id": f"{made_on}:ACME", "ticker": "ACME", "made_on": made_on, "entry_close": 100.0,
        "benchmark_entry_close": 500.0, "call": call, "status": status,
    }


def test_new_prediction_records_entry_prices_and_the_call():
    analysis = Analysis(
        what_happened="x", why="y", no_clear_news=False,
        concept={"name": "Guidance cut", "lesson": "z"},
        prediction={"call": "underperform", "confidence": "low", "reasoning": "r"},
    )
    p = new_prediction(
        "2026-10-02", Company("ACME", "Acme Corp", "Industrials"),
        Quote("ACME", 90.0, 100.0, -10.0, 0), Quote("SPY", 500.0, 498.0, 0.4, 0), analysis,
    )
    assert p["id"] == "2026-10-02:ACME"
    assert (p["entry_close"], p["benchmark_entry_close"]) == (90.0, 500.0)
    assert (p["call"], p["confidence"], p["concept"], p["status"]) == (
        "underperform", "low", "Guidance cut", "open",
    )


def test_due_after_five_trading_days_not_before():
    p = prediction()
    assert due([p], DAYS[:5], "2026-10-01") == []
    assert due([p], DAYS, "2026-10-02") == [p]


def test_due_skips_resolved_predictions():
    assert due([prediction(status="resolved")], DAYS, "2026-10-02") == []


def test_resolve_scores_against_the_benchmark_not_the_raw_move():
    # Stock rose 2% but the market rose 4%, so it underperformed.
    p = prediction(call="underperform")
    resolve(p, close=102.0, benchmark_close=520.0, today="2026-10-02")
    assert p["status"] == "resolved" and p["resolved_on"] == "2026-10-02"
    assert (p["stock_return_pct"], p["benchmark_return_pct"], p["excess_return_pct"]) == (2.0, 4.0, -2.0)
    assert p["outcome"] == "underperform" and p["hit"] is True


def test_resolve_marks_a_miss():
    p = prediction(call="underperform")
    resolve(p, close=110.0, benchmark_close=505.0, today="2026-10-02")
    assert p["outcome"] == "outperform" and p["hit"] is False
