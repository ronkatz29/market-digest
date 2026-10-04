"""Daily job entry point: python -m market_digest.run"""

import argparse
import os
import sys
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import anthropic

from . import scorer
from .analyst import analyze, retrospect
from .finnhub_client import FinnhubClient, FinnhubError, Quote
from .movers import pick_movers
from .store import Store
from .universe import Company, load_universe

BENCHMARK = "SPY"
NEWS_LOOKBACK_DAYS = 3


def scan_quotes(client: FinnhubClient, companies: list[Company]) -> list[Quote]:
    """Quote every company; tickers Finnhub can't price are skipped."""
    quotes = []
    for company in companies:
        try:
            quote = client.quote(company.ticker)
        except FinnhubError as e:
            print(f"skip {company.ticker}: {e}", file=sys.stderr)
            continue
        if quote is not None:
            quotes.append(quote)
    return quotes


def trading_day(quote: Quote) -> str:
    """The US market date a quote belongs to."""
    return datetime.fromtimestamp(quote.timestamp, ZoneInfo("America/New_York")).date().isoformat()


def run(
    finnhub: FinnhubClient,
    claude: anthropic.Anthropic,
    store: Store,
    companies: list[Company],
    force: bool = False,
) -> dict | None:
    """Build and save the digest for the latest trading day. Returns None when it already exists."""
    benchmark = finnhub.quote(BENCHMARK)
    if benchmark is None:
        raise FinnhubError(f"no quote for benchmark {BENCHMARK}")
    day = trading_day(benchmark)
    # On weekends and holidays the latest quote is still the last session's, already digested.
    if store.load_digest(day) is not None and not force:
        print(f"digest for {day} already exists, nothing to do")
        return None

    by_ticker = {c.ticker: c for c in companies}
    quotes = scan_quotes(finnhub, companies)
    closes = {q.ticker: q.price for q in quotes}
    movers = pick_movers(quotes)
    print(f"{day}: scanned {len(quotes)}/{len(companies)} tickers")

    predictions = store.load_predictions()
    end = date.fromisoformat(day)
    entries = []
    for quote in movers.all():
        company = by_ticker[quote.ticker]
        try:
            articles = finnhub.company_news(
                company.ticker, end - timedelta(days=NEWS_LOOKBACK_DAYS), end
            )
            analysis = analyze(claude, company, quote, benchmark, articles, day)
        except Exception as e:
            # One bad stock shouldn't cost the whole day's digest.
            print(f"skip {company.ticker}: {e}", file=sys.stderr)
            continue
        print(f"  {company.ticker:6} {quote.change_pct:+6.2f}%  {analysis.concept.name}")
        titles = {a.url: a for a in articles}
        entries.append(
            {
                "ticker": company.ticker,
                "name": company.name,
                "sector": company.sector,
                "close": quote.price,
                "change_pct": quote.change_pct,
                **analysis.model_dump(exclude={"source_urls"}),
                "sources": [
                    {"headline": titles[u].headline, "source": titles[u].source, "url": u}
                    for u in analysis.source_urls
                ],
            }
        )
        prediction = scorer.new_prediction(day, company, quote, benchmark, analysis)
        predictions = [p for p in predictions if p["id"] != prediction["id"]] + [prediction]

    trading_days = sorted(set(store.digest_dates()) | {day})
    resolved = []
    for prediction in scorer.due(predictions, trading_days, day):
        if prediction["ticker"] not in closes:
            continue
        scorer.resolve(prediction, closes[prediction["ticker"]], benchmark.price, day)
        try:
            prediction["retrospective"] = retrospect(claude, prediction)
        except Exception as e:
            print(f"no retrospective for {prediction['id']}: {e}", file=sys.stderr)
        resolved.append(prediction["id"])
        print(f"  scored {prediction['id']}: {'hit' if prediction['hit'] else 'miss'}")

    digest = {
        "date": day,
        "benchmark": {"ticker": BENCHMARK, "close": benchmark.price, "change_pct": benchmark.change_pct},
        "movers": entries,
        "resolved": resolved,
    }
    store.save_predictions(predictions)
    store.save_digest(day, digest)
    return digest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, help="only scan the first N tickers")
    parser.add_argument("--force", action="store_true", help="rebuild even if today's digest exists")
    args = parser.parse_args()

    run(
        FinnhubClient(os.environ["FINNHUB_API_KEY"]),
        anthropic.Anthropic(),
        Store(),
        load_universe()[: args.limit],
        force=args.force,
    )


if __name__ == "__main__":
    main()
