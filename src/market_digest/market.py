"""Summarise the whole scan: breadth, sector averages and every stock's move."""

from statistics import mean, median

from .finnhub_client import Quote
from .universe import Company


def summarize(quotes: list[Quote], by_ticker: dict[str, Company]) -> dict:
    quotes = [q for q in quotes if q.ticker in by_ticker]
    changes = [q.change_pct for q in quotes]

    by_sector: dict[str, list[float]] = {}
    for quote in quotes:
        by_sector.setdefault(by_ticker[quote.ticker].sector, []).append(quote.change_pct)
    sectors = [
        {
            "sector": sector,
            # Equal-weighted: the average stock in the sector, not the cap-weighted sector index.
            "change_pct": round(mean(moves), 2),
            "advancers": sum(m > 0 for m in moves),
            "decliners": sum(m < 0 for m in moves),
            "count": len(moves),
        }
        for sector, moves in by_sector.items()
    ]
    sectors.sort(key=lambda s: s["change_pct"], reverse=True)

    return {
        "scanned": len(quotes),
        "advancers": sum(c > 0 for c in changes),
        "decliners": sum(c < 0 for c in changes),
        "unchanged": sum(c == 0 for c in changes),
        "median_change_pct": round(median(changes), 2) if changes else 0,
        "sectors": sectors,
        "stocks": [
            {
                "ticker": q.ticker,
                "name": by_ticker[q.ticker].name,
                "sector": by_ticker[q.ticker].sector,
                "close": q.price,
                "change_pct": round(q.change_pct, 2),
            }
            for q in quotes
        ],
    }
