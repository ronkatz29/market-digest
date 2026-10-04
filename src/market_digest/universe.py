"""The S&P 500 ticker list the daily scan runs over."""

import csv
from dataclasses import dataclass
from pathlib import Path

DEFAULT_PATH = Path(__file__).resolve().parents[2] / "data" / "sp500.csv"


@dataclass(frozen=True)
class Company:
    ticker: str
    name: str
    sector: str


def load_universe(path: Path = DEFAULT_PATH) -> list[Company]:
    with open(path, newline="") as f:
        return [Company(r["ticker"], r["name"], r["sector"]) for r in csv.DictReader(f)]
