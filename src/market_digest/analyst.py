"""Explain one mover from its news and make a scoreable prediction."""

import os
from datetime import datetime, timezone
from typing import Literal

import anthropic
from pydantic import BaseModel, Field

from .finnhub_client import Article, Quote
from .universe import Company

DEFAULT_MODEL = "claude-sonnet-5"
MAX_ARTICLES = 40
HORIZON_TRADING_DAYS = 5

SYSTEM_PROMPT = f"""You write one entry of a daily stock market digest for a software \
developer who is learning how news moves stock prices. They invest passively in an S&P 500 \
index fund and are new to analysing individual stocks.

For the stock you are given, use only the supplied articles and price data:

- headline: the main reason for the move in at most eight words, like a news ticker line.
- what_happened: two or three plain sentences on the move itself.
- why: the news that best explains the move. If the articles do not explain it, set \
no_clear_news to true and say so; do not invent a cause. Generic market round-ups that only \
mention the ticker are not an explanation.
- source_urls: the URLs of the articles you relied on, copied exactly. The reader never sees \
the article numbers, so refer to an article by its publisher, not as "article [3]".
- concept: the one market concept this move best illustrates, with a short lesson that \
would still be useful on a different stock. Name it with the standard term in two to four \
words (for example "Guidance cut" or "Profit-taking"), so the same concept gets the same \
name on other days. Define any jargon you use.
- prediction: whether the stock will outperform or underperform the S&P 500 (SPY) over the \
next {HORIZON_TRADING_DAYS} trading days, measured from today's close. Give the reasoning a \
reader could later check against what happened, and a confidence level. Low confidence is \
the honest answer when the evidence is thin.

This is a learning exercise that gets scored later, not investment advice."""


class Concept(BaseModel):
    name: str
    lesson: str


class Prediction(BaseModel):
    call: Literal["outperform", "underperform"]
    confidence: Literal["low", "medium", "high"]
    reasoning: str


class Analysis(BaseModel):
    headline: str
    what_happened: str
    why: str
    no_clear_news: bool
    source_urls: list[str] = Field(default_factory=list)
    concept: Concept
    prediction: Prediction


class AnalystError(Exception):
    pass


def _model(model: str | None) -> str:
    # The variable can be set but empty (e.g. an unset GitHub Actions variable).
    return model or os.environ.get("MARKET_DIGEST_MODEL") or DEFAULT_MODEL


def build_prompt(
    company: Company, quote: Quote, benchmark: Quote, articles: list[Article], day: str
) -> str:
    recent = sorted(articles, key=lambda a: a.published, reverse=True)[:MAX_ARTICLES]
    lines = [
        f"Date: {day}",
        f"Stock: {company.ticker} - {company.name} ({company.sector})",
        f"Close: {quote.price:.2f}, previous close: {quote.prev_close:.2f}, "
        f"change: {quote.change_pct:+.2f}%",
        f"S&P 500 (SPY) change the same day: {benchmark.change_pct:+.2f}%",
        "",
        f"Articles from the last few days ({len(recent)} newest of {len(articles)}):",
    ]
    if not recent:
        lines.append("(none found)")
    for i, a in enumerate(recent, 1):
        when = datetime.fromtimestamp(a.published, timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        lines.append(f"\n[{i}] {a.headline}\n{a.source}, {when}\n{a.summary}\n{a.url}")
    return "\n".join(lines)


def analyze(
    client: anthropic.Anthropic,
    company: Company,
    quote: Quote,
    benchmark: Quote,
    articles: list[Article],
    day: str,
    model: str | None = None,
) -> Analysis:
    response = client.messages.parse(
        model=_model(model),
        max_tokens=16000,
        thinking={"type": "adaptive"},
        output_config={"effort": "medium"},
        system=SYSTEM_PROMPT,
        messages=[
            {"role": "user", "content": build_prompt(company, quote, benchmark, articles, day)}
        ],
        output_format=Analysis,
    )
    analysis = response.parsed_output
    if analysis is None:
        raise AnalystError(f"no analysis for {company.ticker} (stop_reason={response.stop_reason})")
    # Keep only links that were really in the input, so the page never shows an invented URL.
    known = {a.url for a in articles}
    analysis.source_urls = [u for u in analysis.source_urls if u in known]
    return analysis


RETROSPECTIVE_PROMPT = """A prediction from this digest has reached its horizon. In one short \
paragraph for the same reader, say what the original reasoning got right or missed, and what \
to take from it. A single result is weak evidence: do not treat a hit as proof the reasoning \
was sound, or a miss as proof it was wrong.

Stock: {ticker} - {name}
Predicted on {made_on}: {call} vs the S&P 500, {confidence} confidence
Reasoning then: {reasoning}

Result on {resolved_on}: stock {stock_return_pct:+.2f}%, S&P 500 {benchmark_return_pct:+.2f}%, \
so it did {outcome} ({verdict})."""


def retrospect(client: anthropic.Anthropic, prediction: dict, model: str | None = None) -> str:
    """One paragraph on a resolved prediction."""
    response = client.messages.create(
        model=_model(model),
        max_tokens=4000,
        thinking={"type": "adaptive"},
        output_config={"effort": "low"},
        messages=[
            {
                "role": "user",
                "content": RETROSPECTIVE_PROMPT.format(
                    verdict="hit" if prediction["hit"] else "miss", **prediction
                ),
            }
        ],
    )
    return "".join(b.text for b in response.content if b.type == "text").strip()
