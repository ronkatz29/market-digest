import json

from market_digest.store import Store


def test_digest_round_trip_and_index(tmp_path):
    store = Store(tmp_path)
    store.save_digest("2026-10-02", {"date": "2026-10-02", "movers": []})
    store.save_digest("2026-10-01", {"date": "2026-10-01", "movers": []})

    assert store.load_digest("2026-10-02") == {"date": "2026-10-02", "movers": []}
    assert store.load_digest("2026-09-30") is None
    assert store.digest_dates() == ["2026-10-01", "2026-10-02"]
    assert json.loads((tmp_path / "index.json").read_text()) == {
        "dates": ["2026-10-01", "2026-10-02"]
    }


def test_saving_the_same_day_twice_overwrites(tmp_path):
    store = Store(tmp_path)
    store.save_digest("2026-10-02", {"v": 1})
    store.save_digest("2026-10-02", {"v": 2})
    assert store.load_digest("2026-10-02") == {"v": 2}
    assert store.digest_dates() == ["2026-10-02"]


def test_predictions_default_to_empty_and_round_trip(tmp_path):
    store = Store(tmp_path / "new")
    assert store.load_predictions() == []
    store.save_predictions([{"id": "2026-10-02:ACME", "status": "open"}])
    assert store.load_predictions() == [{"id": "2026-10-02:ACME", "status": "open"}]
