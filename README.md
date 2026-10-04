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
| `MARKET_DIGEST_MODEL` | Optional model override |

## Tests

```bash
uv run pytest
```

This is a learning tool, not investment advice.
