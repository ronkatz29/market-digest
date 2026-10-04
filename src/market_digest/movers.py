"""Pick the day's biggest gainers and losers from a set of quotes."""

from dataclasses import dataclass

from .finnhub_client import Quote


@dataclass(frozen=True)
class Movers:
    gainers: list[Quote]
    losers: list[Quote]

    def all(self) -> list[Quote]:
        return self.gainers + self.losers


def pick_movers(quotes: list[Quote], n: int = 3) -> Movers:
    ranked = sorted(quotes, key=lambda q: q.change_pct, reverse=True)
    gainers = [q for q in ranked if q.change_pct > 0][:n]
    # Worst first.
    losers = [q for q in reversed(ranked) if q.change_pct < 0][:n]
    return Movers(gainers, losers)
