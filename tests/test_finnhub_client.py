from datetime import date

import httpx
import pytest

from market_digest.finnhub_client import Article, FinnhubClient, FinnhubError, Quote

QUOTE = {"c": 110.0, "d": 10.0, "dp": 10.0, "h": 111, "l": 99, "o": 100, "pc": 100.0, "t": 1759521600}
NEWS = [
    {"headline": "Acme beats estimates", "summary": "Strong quarter.", "source": "Reuters",
     "url": "https://example.com/a", "datetime": 1759500000},
    {"headline": "", "summary": "dropped", "source": "x", "url": "", "datetime": 1},
]


def make_client(handler, **kwargs):
    sleeps = []
    client = FinnhubClient(
        "key",
        http=httpx.Client(transport=httpx.MockTransport(handler)),
        sleep=sleeps.append,
        **kwargs,
    )
    return client, sleeps


def test_quote_parses_response_and_sends_token():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=QUOTE)

    client, _ = make_client(handler)
    assert client.quote("ACME") == Quote("ACME", 110.0, 100.0, 10.0, 1759521600)
    assert seen == {"symbol": "ACME", "token": "key"}


def test_quote_returns_none_for_unknown_symbol():
    zeros = {"c": 0, "d": None, "dp": None, "h": 0, "l": 0, "o": 0, "pc": 0, "t": 0}
    client, _ = make_client(lambda r: httpx.Response(200, json=zeros))
    assert client.quote("NOPE") is None


def test_company_news_parses_and_drops_headless_items():
    seen = {}

    def handler(request):
        seen.update(request.url.params)
        return httpx.Response(200, json=NEWS)

    client, _ = make_client(handler)
    articles = client.company_news("ACME", date(2026, 10, 1), date(2026, 10, 4))
    assert articles == [
        Article("Acme beats estimates", "Strong quarter.", "Reuters", "https://example.com/a", 1759500000)
    ]
    assert seen["from"] == "2026-10-01" and seen["to"] == "2026-10-04"


def test_retries_after_rate_limit():
    responses = iter([httpx.Response(429), httpx.Response(200, json=QUOTE)])
    client, sleeps = make_client(lambda r: next(responses))
    assert client.quote("ACME").price == 110.0
    assert 5 in sleeps


def test_gives_up_after_repeated_failures():
    client, _ = make_client(lambda r: httpx.Response(503))
    with pytest.raises(FinnhubError):
        client.quote("ACME")


def test_client_error_raises_immediately():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(401, text="bad key")

    client, _ = make_client(handler)
    with pytest.raises(FinnhubError):
        client.quote("ACME")
    assert len(calls) == 1


def test_paces_calls_under_the_rate_limit():
    now = [0.0]
    client, sleeps = make_client(
        lambda r: httpx.Response(200, json=QUOTE), clock=lambda: now[0], min_interval=1.0
    )
    client.quote("A")
    now[0] = 0.25
    client.quote("B")
    assert sleeps == [0.75]
