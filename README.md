# Market Digest

A daily learning tool: finds the biggest S&P 500 movers, explains why they moved from the
news, makes a 5-day prediction against the S&P 500, and scores that prediction later.

Design: [docs/specs/2026-10-04-market-digest-design.md](docs/specs/2026-10-04-market-digest-design.md)

## Setup

```bash
uv sync
```

Environment variables:

| Variable | Purpose |
|---|---|
| `FINNHUB_API_KEY` | Free key from https://finnhub.io/register |
| `ANTHROPIC_API_KEY` | Claude API key for the explanations and predictions |
| `MARKET_DIGEST_MODEL` | Optional model override (default `claude-sonnet-5`) |

## Run

```bash
uv run python -m market_digest.run           # build the digest for the latest trading day
uv run python -m market_digest.run --force   # rebuild it even if it already exists
uv run python -m market_digest.run --limit 30  # quick run over the first 30 tickers
```

A full run takes about 12 minutes: the Finnhub free tier allows 60 calls a minute and the
scan quotes all ~500 tickers. Output goes to `site/data/`.

View the site locally:

```bash
python3 -m http.server 8000 --directory site
```

## How it works

1. `universe.py` loads the S&P 500 list from `data/sp500.csv`.
2. `finnhub_client.py` quotes every ticker and SPY.
3. `movers.py` picks the top 3 gainers and top 3 losers.
4. `analyst.py` makes one Claude call per mover: what happened, why, a concept, a prediction.
5. `scorer.py` scores predictions that are 5 trading days old against SPY.
6. `store.py` writes the JSON that the static site in `site/` reads.

`.github/workflows/daily.yml` runs this on weekdays after the US close, commits the new data,
and deploys `site/` to GitHub Pages. It needs `FINNHUB_API_KEY` and `ANTHROPIC_API_KEY` as
repository secrets.

## Tests

```bash
uv run pytest
```

This is a learning tool, not investment advice.
