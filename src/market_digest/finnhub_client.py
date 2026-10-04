"""Thin Finnhub client: quotes and company news, paced for the free tier."""

import time
from dataclasses import dataclass
from datetime import date
from typing import Callable

import httpx

BASE_URL = "https://finnhub.io/api/v1"
# Free tier allows 60 calls/minute; stay a little under it.
MIN_INTERVAL_SECONDS = 1.1
MAX_RETRIES = 4


class FinnhubError(Exception):
    pass


@dataclass(frozen=True)
class Quote:
    ticker: str
    price: float
    prev_close: float
    change_pct: float
    timestamp: int  # unix seconds of the last trade


@dataclass(frozen=True)
class Article:
    headline: str
    summary: str
    source: str
    url: str
    published: int  # unix seconds


class FinnhubClient:
    def __init__(
        self,
        api_key: str,
        http: httpx.Client | None = None,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        min_interval: float = MIN_INTERVAL_SECONDS,
    ):
        self._api_key = api_key
        self._http = http or httpx.Client(timeout=15)
        self._sleep = sleep
        self._clock = clock
        self._min_interval = min_interval
        self._last_call: float | None = None

    def quote(self, ticker: str) -> Quote | None:
        """Latest quote, or None when Finnhub has no data for the ticker."""
        data = self._get("/quote", {"symbol": ticker})
        # Unknown symbols come back as all zeros rather than an error.
        if not data.get("c") or not data.get("pc"):
            return None
        return Quote(
            ticker=ticker,
            price=data["c"],
            prev_close=data["pc"],
            change_pct=data["dp"],
            timestamp=data["t"],
        )

    def company_news(self, ticker: str, start: date, end: date) -> list[Article]:
        data = self._get(
            "/company-news",
            {"symbol": ticker, "from": start.isoformat(), "to": end.isoformat()},
        )
        return [
            Article(
                headline=a["headline"],
                summary=a.get("summary", ""),
                source=a.get("source", ""),
                url=a.get("url", ""),
                published=a["datetime"],
            )
            for a in data
            if a.get("headline")
        ]

    def _get(self, path: str, params: dict):
        for attempt in range(MAX_RETRIES):
            self._pace()
            resp = self._http.get(
                BASE_URL + path, params={**params, "token": self._api_key}
            )
            if resp.status_code == 429 or resp.status_code >= 500:
                self._sleep(2**attempt * 5)
                continue
            if resp.status_code != 200:
                raise FinnhubError(f"{path} returned {resp.status_code}: {resp.text[:200]}")
            return resp.json()
        raise FinnhubError(f"{path} still failing after {MAX_RETRIES} attempts")

    def _pace(self) -> None:
        now = self._clock()
        if self._last_call is not None:
            wait = self._min_interval - (now - self._last_call)
            if wait > 0:
                self._sleep(wait)
                now += wait
        self._last_call = now
