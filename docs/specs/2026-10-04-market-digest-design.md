# Market Digest — daily "why did it move" learning tool

## Context

Ron invests passively (about $70k in the S&P 500, $20-30k in an Israeli קרן כספית) and wants to
build real understanding of how news moves stocks. The tool is for **learning**, not for
real-money decisions.

Decisions made in brainstorming:

| Topic | Decision |
|---|---|
| Goal | Teach me the market |
| Format | Daily digest on a web page, with an archive |
| Coverage | Biggest S&P 500 movers of the day and the news behind them |
| Forward-looking part | The LLM makes a reasoned prediction per mover; the tool scores it later |
| Budget | Free data tiers; LLM cost of a few cents a day |
| Stack | Python |
| Hosting | GitHub Actions daily cron + GitHub Pages (public repo and site) |
| LLM design | Fixed pipeline, one structured call per stock (no agent loop in v1) |

Defaults I chose (change any of them):

- **6 movers a day**: top 3 gainers and top 3 losers by daily % change.
- **Prediction**: will the stock *outperform or underperform the S&P 500 (SPY) over the next
  5 trading days*, with a confidence level and reasoning. Measuring against SPY teaches the
  benchmark idea and removes "the whole market went up" noise.
- **Project location**: new git repo at `~/market-digest`.

## How it works

```
GitHub Actions cron (Mon-Fri, after US close)
  1. universe   -> S&P 500 ticker list (CSV in repo)
  2. prices     -> Finnhub /quote for each ticker + SPY (throttled under 60/min, ~9 min)
  3. movers     -> top 3 up, top 3 down
  4. news       -> Finnhub /company-news, last 3 days, per mover
  5. analyst    -> one Claude call per mover, structured output
  6. scorer     -> score predictions that are now 5 trading days old
  7. store      -> write JSON, commit, deploy Pages
```

**Analyst output per stock** (structured JSON):
- `what_happened`: 2-3 sentences, plain language
- `why`: the news driver, with links to the source articles
- `concept`: name plus a short lesson (e.g. "guidance cut", "rate sensitivity")
- `prediction`: `outperform | underperform` vs SPY, confidence (low/med/high), reasoning
- `no_clear_news: true` when the articles don't explain the move, instead of inventing a cause

**Scorer**: compares stock return to SPY return from prediction-day close to the close 5
trading days later, marks hit or miss, and adds a one-paragraph LLM retrospective ("what the
reasoning got right or missed"). This retrospective is the main learning payoff.

**Web page** (static, vanilla HTML + JS, no build step):
- Today's digest: 6 cards
- Archive by date
- Scoreboard: hit rate overall, by confidence level, and by concept, plus the list of
  resolved predictions with retrospectives

## Files

```
~/market-digest/
  data/sp500.csv                     ticker, name, sector
  src/market_digest/
    universe.py                      load ticker list
    finnhub_client.py                quote + company-news, rate limiting, retries
    movers.py                        rank by % change
    analyst.py                       Claude call + output schema
    scorer.py                        resolve due predictions + retrospective
    store.py                         read/write JSON
    run.py                           orchestrates the daily job
  site/
    index.html, app.js, style.css
    data/digests/YYYY-MM-DD.json
    data/predictions.json
  tests/                             pytest, recorded API fixtures
  .github/workflows/daily.yml        cron + commit data + deploy Pages
  docs/specs/2026-10-04-market-digest-design.md
  pyproject.toml, README.md
```

## Build order (confirm each step works before the next)

1. **Scaffold + spec**: repo, `pyproject.toml`, save this design as the spec file.
2. **Finnhub client**: get a free key; confirm `/quote` works for a stock and for SPY, and
   `/company-news` returns articles. If SPY is not on the free tier, use the average of the
   500 quotes or `^GSPC` via yfinance as the benchmark.
3. **Movers**: scan the 500 tickers, print the top 3 up and down. Skip the run when the quote
   timestamp is not today (market holiday).
4. **Analyst**: load the `claude-api` skill and verify the current model ID and structured
   output API first. Model is set by env var; default per CLAUDE.md is `claude-sonnet-4-6`,
   and `claude-sonnet-5` is the newer option to check.
5. **Store + scorer**: write digest and predictions JSON; score with a backdated fixture.
6. **Site**: three views reading the JSON.
7. **GitHub Actions**: workflow with `FINNHUB_API_KEY` and `ANTHROPIC_API_KEY` as repo
   secrets; run it manually once with `workflow_dispatch`, then enable the cron.

Tests are written with each module (TDD), using saved API responses so they run offline.

## v2: whole-market dashboard and more movers

- **10 movers a day**: top 5 gainers and top 5 losers get the full LLM analysis (10 Claude
  calls), replacing the 6 above.
- **`market.py`** keeps the full scan instead of discarding it. Each digest gets a `market`
  block: `scanned`, `advancers`, `decliners`, `unchanged`, `median_change_pct`, `sectors`
  (equal-weighted average move, best first) and `stocks` (ticker, name, sector, close,
  change for every stock). No extra API calls.
- **Page**: stat tiles, a breadth bar, sector bars and a heatmap of every stock grouped by
  sector sit above the stories; "Top 20 up" and "Top 20 down" tables sit below them. Plain
  DOM and CSS, no chart library. Digests without a `market` block render as before.
- Sector figures are the average stock in the sector, not the cap-weighted sector index.

## Things to know

- The repo and site are **public** on free GitHub Pages. They hold only market data and LLM
  text, nothing about Ron's own holdings.
- The workflow's bot commits daily data. Ron's rule still holds for code: no commit or push
  from me unless asked. Creating the GitHub repo and the first push need Ron's go-ahead.
- Six predictions a day is a small sample. The hit rate will be noisy for weeks; treat it as
  a way to study reasoning, not as proof the model can pick stocks.
- Finnhub's free tier is for personal, non-commercial use.

## Out of scope for v1

Chat/agent mode, personal watchlist, macro section, historical pattern stats, email or
WhatsApp delivery, Israeli market. Each can be added later; the pipeline + agent option is the
natural next step for agent practice.

## Verification

- `pytest` passes offline.
- `python -m market_digest.run --dry-run` locally prints 6 movers with explanations and
  predictions, and makes no more than 6 LLM calls.
- A real local run writes `site/data/digests/<today>.json`; opening `site/index.html` through
  `python -m http.server` shows the 6 cards with working article links.
- A fixture prediction dated 5 trading days back gets scored and appears on the scoreboard.
- Manual `workflow_dispatch` run on GitHub finishes green and the Pages URL shows the digest.
