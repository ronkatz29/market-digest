"""Email a summary of the latest digest: python -m market_digest.notify"""

import os
import smtplib
from email.message import EmailMessage

from .store import Store

GMAIL_HOST = "smtp.gmail.com"
GMAIL_PORT = 465


def _mover_line(mover: dict) -> str:
    return f"  {mover['ticker']:6} {mover['change_pct']:+6.2f}%  {mover['headline']}"


def build_email(digest: dict, predictions: list[dict], site_url: str, address: str) -> EmailMessage:
    """The day's summary as an email from address to itself."""
    day = digest["date"]
    benchmark = digest["benchmark"]
    movers = sorted(digest["movers"], key=lambda m: m["change_pct"], reverse=True)
    gainers = [m for m in movers if m["change_pct"] > 0]
    losers = [m for m in reversed(movers) if m["change_pct"] <= 0]

    lines = ["Gainers", *map(_mover_line, gainers), "", "Losers", *map(_mover_line, losers), ""]
    scored = [p for p in predictions if p["id"] in set(digest["resolved"])]
    if scored:
        hits = sum(1 for p in scored if p["hit"])
        noun = "prediction" if len(scored) == 1 else "predictions"
        lines += [f"Scored today: {len(scored)} {noun} ({hits} hit, {len(scored) - hits} miss)", ""]
    lines.append(f"Full digest: {site_url.rstrip('/')}/#/d/{day}")

    message = EmailMessage()
    message["Subject"] = (
        f"Market Digest {day} · {benchmark['ticker']} {benchmark['change_pct']:+.2f}%"
    )
    message["From"] = address
    message["To"] = address
    message.set_content("\n".join(lines))
    return message


def send_latest(
    store: Store, site_url: str, address: str, app_password: str, smtp=smtplib.SMTP_SSL
) -> None:
    """Email the newest digest in the store through Gmail."""
    day = store.digest_dates()[-1]
    message = build_email(store.load_digest(day), store.load_predictions(), site_url, address)
    with smtp(GMAIL_HOST, GMAIL_PORT) as server:
        server.login(address, app_password)
        server.send_message(message)
    print(f"emailed digest for {day}")


def main() -> None:
    send_latest(
        Store(),
        os.environ["SITE_URL"],
        os.environ["GMAIL_ADDRESS"],
        os.environ["GMAIL_APP_PASSWORD"],
    )


if __name__ == "__main__":
    main()
