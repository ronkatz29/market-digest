from market_digest.notify import build_email, send_latest
from market_digest.store import Store

SITE = "https://example.github.io/market-digest/"
ME = "me@example.com"


def mover(ticker, change_pct, headline):
    return {"ticker": ticker, "change_pct": change_pct, "headline": headline}


def digest(**overrides):
    return {
        "date": "2026-10-02",
        "benchmark": {"ticker": "SPY", "close": 769.64, "change_pct": 0.7395},
        "movers": [
            mover("HPE", 7.41, "Vultr order lifts HPE"),
            mover("TER", 7.9968, "Weak jobs data lifts chip stocks"),
            mover("ACME", -3.2, "Guidance cut"),
            mover("ZZZ", -9.05, "Lawsuit filed"),
        ],
        "resolved": [],
        **overrides,
    }


def body(message):
    return message.get_content()


def test_subject_has_the_date_and_the_benchmark_move():
    message = build_email(digest(), [], SITE, ME)
    assert message["Subject"] == "Market Digest 2026-10-02 · SPY +0.74%"


def test_message_goes_from_and_to_the_same_address():
    message = build_email(digest(), [], SITE, ME)
    assert message["From"] == ME
    assert message["To"] == ME


def test_gainers_and_losers_are_listed_biggest_move_first():
    lines = body(build_email(digest(), [], SITE, ME)).splitlines()
    gainers, losers = lines.index("Gainers"), lines.index("Losers")
    assert lines[gainers + 1 : gainers + 3] == [
        "  TER     +8.00%  Weak jobs data lifts chip stocks",
        "  HPE     +7.41%  Vultr order lifts HPE",
    ]
    assert lines[losers + 1 : losers + 3] == [
        "  ZZZ     -9.05%  Lawsuit filed",
        "  ACME    -3.20%  Guidance cut",
    ]


def test_links_to_that_days_page_on_the_site():
    text = body(build_email(digest(), [], SITE, ME))
    assert "Full digest: https://example.github.io/market-digest/#/d/2026-10-02" in text


def test_counts_hits_and_misses_among_predictions_scored_today():
    predictions = [
        {"id": "2026-09-25:AAA", "hit": True},
        {"id": "2026-09-25:BBB", "hit": False},
        {"id": "2026-09-25:CCC", "hit": True},
        {"id": "2026-09-24:OLD", "hit": False},
    ]
    resolved = ["2026-09-25:AAA", "2026-09-25:BBB", "2026-09-25:CCC"]
    text = body(build_email(digest(resolved=resolved), predictions, SITE, ME))
    assert "Scored today: 3 predictions (2 hit, 1 miss)" in text


def test_no_scored_line_when_nothing_was_scored():
    assert "Scored today" not in body(build_email(digest(), [], SITE, ME))


class FakeSMTP:
    """Stands in for smtplib.SMTP_SSL and records what it was asked to do."""

    def __init__(self, host, port):
        self.server = (host, port)
        self.logins = []
        self.sent = []
        FakeSMTP.last = self

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def login(self, user, password):
        self.logins.append((user, password))

    def send_message(self, message):
        self.sent.append(message)


def test_send_latest_emails_the_newest_digest_through_gmail(tmp_path):
    store = Store(tmp_path)
    store.save_digest("2026-10-01", digest(date="2026-10-01"))
    store.save_digest("2026-10-02", digest())

    send_latest(store, SITE, ME, "app-password", smtp=FakeSMTP)

    smtp = FakeSMTP.last
    assert smtp.server == ("smtp.gmail.com", 465)
    assert smtp.logins == [(ME, "app-password")]
    assert [m["Subject"] for m in smtp.sent] == ["Market Digest 2026-10-02 · SPY +0.74%"]
