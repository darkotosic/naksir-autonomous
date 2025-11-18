# cron_jobs/morning_run.py
import os
import sys
import json
from datetime import datetime, date

# Dodaj root projekta u sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core_data.ingest import fetch_all_data
from core_data.cache import read_json
from builders.engine import build_all_ticket_sets
from outputs.pages_writer import write_tickets_json
from outputs.telegram_bot import send_message  # opcioni output

TELEGRAM_MORNING_CHAT_ID = os.getenv("TELEGRAM_MORNING_CHAT_ID", "")


def _format_ticket_markdown(ticket: dict, set_label: str) -> str:
    """
    Format za Telegram poruku.
    """
    lines = []
    lines.append(f"🎫 *{set_label} — {ticket['ticket_id']}*")
    lines.append(f"🔢 Ukupna kvota: *{ticket['total_odds']:.2f}*")
    lines.append("")

    for leg in ticket["legs"]:
        lines.append(f"🏟 {leg['league_name']} — {leg['league_country']}")
        lines.append(f"⚽ {leg['home']} vs {leg['away']}")
        lines.append(f"⏰ {leg['kickoff']}")
        lines.append(
            f"🎯 {leg['pick']} @ *{leg['odds']:.2f}*  "
            f"({leg['market']}/{leg['market_family']})"
        )
        lines.append("")

    return "\n".join(lines).strip()


def main() -> None:
    print(f"[{datetime.utcnow().isoformat()}] Morning run start")

    # 1) Ingest + cache (fixtures, odds, standings, stats, h2h)
    summary = fetch_all_data(days_ahead=2)
    print("[INGEST] Summary:")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    # 2) Učitaj današnje fixtures + odds iz cache
    today = date.today()
    fixtures = read_json("fixtures.json", day=today) or []
    odds = read_json("odds.json", day=today) or []

    if not fixtures or not odds:
        print("[ERROR] Missing fixtures or odds for today – skipping ticket build.")
        return

    # 3) LAYER 2 – build all ticket sets (10 setova, fallback logika u engine-u)
    ticket_sets = build_all_ticket_sets(fixtures, odds)
    print("[ENGINE] Ticket sets:")
    print(json.dumps(ticket_sets, ensure_ascii=False, indent=2))

    # 4) Zapiši tickets.json za Pages / frontend
    write_tickets_json(ticket_sets)
    print("[PAGES] tickets.json written.")

    # 5) Opcioni Telegram output – npr. šaljemo samo tikete iz setova sa status != NO_DATA
    if TELEGRAM_MORNING_CHAT_ID:
        for s in ticket_sets.get("sets", []):
            if s.get("status") == "NO_DATA":
                continue
            for t in s.get("tickets", []):
                text = _format_ticket_markdown(t, s.get("label", s.get("code", "")))
                print(
                    f"[TELEGRAM] Sending ticket {t['ticket_id']} "
                    f"({s['code']}) to {TELEGRAM_MORNING_CHAT_ID}"
                )
                send_message(
                    chat_id=TELEGRAM_MORNING_CHAT_ID,
                    text=text,
                    parse_mode="Markdown",
                )

    print(f"[{datetime.utcnow().isoformat()}] Morning run done")


if __name__ == "__main__":
    main()
