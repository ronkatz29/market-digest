from types import SimpleNamespace

import pytest

from market_digest.analyst import (
    MAX_ARTICLES,
    Analysis,
    AnalystError,
    analyze,
    build_prompt,
)
from market_digest.finnhub_client import Article, Quote
from market_digest.universe import Company

COMPANY = Company("ACME", "Acme Corp", "Industrials")
QUOTE = Quote("ACME", 90.0, 100.0, -10.0, 0)
SPY = Quote("SPY", 500.0, 498.0, 0.4, 0)
ARTICLES = [
    Article("Acme cuts guidance", "Lower full-year outlook.", "Reuters", "https://example.com/a", 200),
    Article("Old story", "Earlier.", "Yahoo", "https://example.com/b", 100),
]


def analysis(urls):
    return Analysis(
        headline="h", what_happened="Fell 10%.",
        why="Guidance cut.",
        no_clear_news=False,
        source_urls=urls,
        concept={"name": "Guidance cut", "lesson": "Outlook matters more than past results."},
        prediction={"call": "underperform", "confidence": "medium", "reasoning": "Drift."},
    )


class FakeClient:
    def __init__(self, parsed, stop_reason="end_turn"):
        self.calls = []
        self.messages = SimpleNamespace(parse=self._parse)
        self._response = SimpleNamespace(parsed_output=parsed, stop_reason=stop_reason)

    def _parse(self, **kwargs):
        self.calls.append(kwargs)
        return self._response


def test_prompt_has_price_context_and_newest_article_first():
    prompt = build_prompt(COMPANY, QUOTE, SPY, list(reversed(ARTICLES)), "2026-10-02")
    assert "ACME - Acme Corp (Industrials)" in prompt
    assert "change: -10.00%" in prompt
    assert "SPY) change the same day: +0.40%" in prompt
    assert prompt.index("Acme cuts guidance") < prompt.index("Old story")
    assert "https://example.com/a" in prompt


def test_prompt_says_when_there_is_no_news():
    assert "(none found)" in build_prompt(COMPANY, QUOTE, SPY, [], "2026-10-02")


def test_prompt_caps_articles_and_states_the_cap():
    many = [Article(f"h{i}", "", "s", f"https://example.com/{i}", i) for i in range(MAX_ARTICLES + 5)]
    prompt = build_prompt(COMPANY, QUOTE, SPY, many, "2026-10-02")
    assert f"({MAX_ARTICLES} newest of {MAX_ARTICLES + 5})" in prompt
    assert "] h4\n" not in prompt and "] h5\n" in prompt


def test_analyze_returns_parsed_output_and_drops_unknown_urls():
    client = FakeClient(analysis(["https://example.com/a", "https://invented.example/x"]))
    result = analyze(client, COMPANY, QUOTE, SPY, ARTICLES, "2026-10-02", model="m")
    assert result.source_urls == ["https://example.com/a"]
    assert result.prediction.call == "underperform"
    call = client.calls[0]
    assert call["model"] == "m" and call["output_format"] is Analysis


def test_analyze_raises_when_nothing_parsed():
    client = FakeClient(None, stop_reason="refusal")
    with pytest.raises(AnalystError, match="refusal"):
        analyze(client, COMPANY, QUOTE, SPY, ARTICLES, "2026-10-02", model="m")
