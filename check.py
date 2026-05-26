#!/usr/bin/env python3
"""
Monitor Fever page for F1 Madrid 2026 "Entrada General" ticket availability.
Sends an email via Gmail SMTP when any tracked ticket becomes available.
"""
import json
import os
import re
import smtplib
import sys
from email.message import EmailMessage
from pathlib import Path
from urllib.request import Request, urlopen

FEVER_URL = (
    "https://feverup.com/m/432252/en?thm=5513"
    "&cp_landing_source=www.madring"
    "&session_ids=450963725"
)

TRACKED_TICKET_IDS = {
    450963725: "Standing Area Second Release (€295)",
    284360367: "Section 17 Pelouse Final Call (€397)",
}

STATE_FILE = Path("state.json")
USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)


def fetch_page() -> str:
    req = Request(FEVER_URL, headers={"User-Agent": USER_AGENT, "Accept-Language": "en"})
    with urlopen(req, timeout=30) as resp:
        return resp.read().decode("utf-8", errors="replace")


def extract_state(html: str) -> dict:
    match = re.search(
        r'<script[^>]*id="astro-tools-transfer-state"[^>]*>(.+?)</script>',
        html,
        re.DOTALL,
    )
    if not match:
        raise RuntimeError("astro-tools-transfer-state script not found in page")
    return json.loads(match.group(1))


def find_tickets(state: dict) -> dict[int, dict]:
    ts = state["ticket-selector-config"]["transferState"]
    inner = ts[next(iter(ts))]
    found = {}
    for zone in inner["level"]["items"]:
        for pass_group in zone["level"]["items"]:
            for ticket in pass_group["level"]["items"]:
                value = ticket.get("value", {})
                tid = value.get("id")
                if tid in TRACKED_TICKET_IDS:
                    found[tid] = {
                        "label": value.get("label_without_format", ""),
                        "price": value.get("price"),
                        "available_tickets": value.get("available_tickets", 0),
                        "has_available_tickets": value.get("has_available_tickets", False),
                        "zone": zone.get("default_label", ""),
                    }
    return found


def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except json.JSONDecodeError:
            pass
    return {}


def save_state(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, indent=2))


def send_email(subject: str, body: str) -> None:
    smtp_user = os.environ["SMTP_USER"]
    smtp_pass = os.environ["SMTP_PASS"]
    to_addr = os.environ["NOTIFY_EMAIL"]
    msg = EmailMessage()
    msg["From"] = smtp_user
    msg["To"] = to_addr
    msg["Subject"] = subject
    msg.set_content(body)
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=30) as smtp:
        smtp.login(smtp_user, smtp_pass)
        smtp.send_message(msg)


def main() -> int:
    if "--test-email" in sys.argv:
        body = (
            "This is a test email from the F1 Madrid ticket monitor.\n\n"
            "If you got this, SMTP and GitHub Secrets are wired up correctly.\n"
            "Real alerts will look like this and include direct buy links."
        )
        try:
            send_email("F1 Madrid monitor — test email", body)
            print(f"Test email sent to {os.environ.get('NOTIFY_EMAIL')}")
            return 0
        except Exception as exc:
            print(f"ERROR sending test email: {exc}", file=sys.stderr)
            return 3

    try:
        html = fetch_page()
        state = extract_state(html)
        tickets = find_tickets(state)
    except Exception as exc:
        print(f"ERROR fetching/parsing page: {exc}", file=sys.stderr)
        return 1

    if not tickets:
        print("Tracked tickets not found on the page — Fever may have changed the layout.")
        return 2

    previous = load_state()
    new_state: dict[str, dict] = {}
    newly_available: list[tuple[int, dict]] = []

    for tid, info in tickets.items():
        new_state[str(tid)] = info
        was_available = previous.get(str(tid), {}).get("has_available_tickets", False)
        is_available = info["has_available_tickets"]
        status = "AVAILABLE" if is_available else "sold out"
        print(f"[{tid}] {info['label']}  zone='{info['zone']}'  €{info['price']}  -> {status}  (avail={info['available_tickets']})")
        if is_available and not was_available:
            newly_available.append((tid, info))

    save_state(new_state)

    if newly_available:
        lines = [
            "🎉 F1 Madrid 2026 — Entrada General tickets are available!",
            "",
            "Buy here:",
            f"  {FEVER_URL}",
            "",
            "Tickets that just became available:",
        ]
        for tid, info in newly_available:
            lines.append(
                f"  • {info['label']} — €{info['price']} "
                f"({info['available_tickets']} available)"
            )
        lines.append("")
        lines.append("Hurry — these usually go fast!")
        body = "\n".join(lines)
        subject = f"F1 Madrid: {len(newly_available)} Entrada General ticket(s) available!"
        try:
            send_email(subject, body)
            print(f"Email sent to {os.environ.get('NOTIFY_EMAIL')}")
        except Exception as exc:
            print(f"ERROR sending email: {exc}", file=sys.stderr)
            return 3

    return 0


if __name__ == "__main__":
    sys.exit(main())
