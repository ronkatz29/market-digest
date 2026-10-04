"""Open predictions for today's movers and score the ones that have reached their horizon."""

from .analyst import HORIZON_TRADING_DAYS, Analysis
from .finnhub_client import Quote
from .universe import Company


def new_prediction(
    day: str, company: Company, quote: Quote, benchmark: Quote, analysis: Analysis
) -> dict:
    return {
        "id": f"{day}:{company.ticker}",
        "ticker": company.ticker,
        "name": company.name,
        "made_on": day,
        "entry_close": quote.price,
        "benchmark_entry_close": benchmark.price,
        "call": analysis.prediction.call,
        "confidence": analysis.prediction.confidence,
        "reasoning": analysis.prediction.reasoning,
        "concept": analysis.concept.name,
        "status": "open",
    }


def due(predictions: list[dict], trading_days: list[str], today: str) -> list[dict]:
    """Open predictions made at least HORIZON_TRADING_DAYS trading days before today.

    trading_days is every day the job has run, oldest first, including today.
    """
    position = {day: i for i, day in enumerate(trading_days)}
    return [
        p
        for p in predictions
        if p["status"] == "open"
        and p["made_on"] in position
        and position[today] - position[p["made_on"]] >= HORIZON_TRADING_DAYS
    ]


def resolve(prediction: dict, close: float, benchmark_close: float, today: str) -> None:
    """Score a prediction in place against today's closes."""
    stock_return = close / prediction["entry_close"] - 1
    benchmark_return = benchmark_close / prediction["benchmark_entry_close"] - 1
    excess = stock_return - benchmark_return
    outcome = "outperform" if excess > 0 else "underperform"
    prediction.update(
        status="resolved",
        resolved_on=today,
        exit_close=close,
        benchmark_exit_close=benchmark_close,
        stock_return_pct=round(stock_return * 100, 2),
        benchmark_return_pct=round(benchmark_return * 100, 2),
        excess_return_pct=round(excess * 100, 2),
        outcome=outcome,
        hit=outcome == prediction["call"],
    )
