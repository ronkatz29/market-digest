"""JSON files the static site reads: one digest per day plus a running predictions list."""

import json
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[2] / "site" / "data"


class Store:
    def __init__(self, data_dir: Path = DEFAULT_DATA_DIR):
        self._dir = data_dir
        self._digests = data_dir / "digests"
        self._predictions = data_dir / "predictions.json"
        self._index = data_dir / "index.json"

    def save_digest(self, day: str, digest: dict) -> None:
        self._digests.mkdir(parents=True, exist_ok=True)
        _write(self._digests / f"{day}.json", digest)
        # The site can't list a directory, so keep an index of available days.
        _write(self._index, {"dates": self.digest_dates()})

    def load_digest(self, day: str) -> dict | None:
        path = self._digests / f"{day}.json"
        return json.loads(path.read_text()) if path.exists() else None

    def digest_dates(self) -> list[str]:
        """Days with a digest, oldest first."""
        return sorted(p.stem for p in self._digests.glob("*.json"))

    def load_predictions(self) -> list[dict]:
        if not self._predictions.exists():
            return []
        return json.loads(self._predictions.read_text())

    def save_predictions(self, predictions: list[dict]) -> None:
        self._dir.mkdir(parents=True, exist_ok=True)
        _write(self._predictions, predictions)


def _write(path: Path, data) -> None:
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n")
