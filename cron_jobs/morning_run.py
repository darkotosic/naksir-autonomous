# cron_jobs/morning_run.py
from __future__ import annotations

import os
import sys
import json
from datetime import datetime, date
from typing import Any, Dict, List

# Dodaj root projekta u sys.path
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core_data.ingest import fetch_all_data
from core_data.cache import read_json
from builders.engine import build_all_ticket_sets
from outputs.pages_writer import write_tickets_json
from outputs.telegram_bot import send_message
from ai_engine.meta import annotate_ticket_sets_with_score


TELEGRAM_MORNING_CHAT_ID = os.getenv("TELEGRAM_MORNING_CHAT_ID", "").strip()


def _normalize_items(raw: Any) -> List[Dict[str, Any]]:
    """
    Normalizuje fixtures/odds payload na listu dict-ova.

    Podržava:
      - već clean-ovane liste
      - dict sa 'response' listom (legacy API shape)
      - dict sa 'data' ili 'fixtures' listom (fallback)
    """
    if raw is None:
        return []

    # Već lista
    if isinstance(raw, list):
        return [x for x in raw if isinstance(x, dict)]

    if isinstance(raw, dict):
        for key in ("response", "fixtures", "data"):
            val = raw.get(key)
            if isinstance(val, list):
                return [x for x in val if isinstance(x, dict)]

    # Fallback: ništa smisleno
    return []


def _format_ticket_message(ticket_set: Dict[str, Any], ticket: Dict[str, Any]) -> str:
    """
    Formatira jedan tiket u tekst spreman za Telegram.
    """
    set_label = ticket_set.get("label") or "[TICKET SET]"
    set_code = ticket_set.get("code") or "SET"
    ticket_id = ticket.get("ticket_id") or "?"
    total_odds = float(ticket.get("total_odds", 0.0) or 0.0)

    lines: List[str] = []
    lines.append(f"🎫 {set_label} — Ticket {ticket_id}")
    lines.append(f"📅 {date.today().isoformat()}  |  Set: {set_code}")
    if total_odds > 0:
        lines.append(f"📈 Total odds: {total_odds:.2f}")
    lines.append("")

    for leg in ticket.get("legs", []):
        league_name = leg.get("league_name") or ""
        league_country = leg.get("league_country") or ""
        home = leg.get("home") or ""
        away = leg.get("away") or ""
        kickoff = leg.get("kickoff") or ""
        market = leg.get("market") or ""
        pick = leg.get("pick") or ""
        odds = leg.get("odds")

        lines.append(f"🏟 {league_name} ({league_country})")
        lines.append(f"⚽ {home} vs {away}")
        lines.append(f"⏰ {kickoff}")
        if odds is not None:
            lines.append(f"🎯 {market} — {pick} @ {float(odds):.2f}")
        else:
            lines.append(f"🎯 {market} — {pick}")
        lines.append("")

    return "\n".join(lines).strip()


def main() -> None:
    utc_now = datetime.utcnow().isoformat() + "Z"
    print(f"[{utc_now}] Morning run started")

    # 1) Full ingest (fixtures/odds/standings/stats/h2h...)
    try:
        ingest_summary = fetch_all_data(days_ahead=2)
        print(f"[INGEST] Done. Summary: {json.dumps(ingest_summary, ensure_ascii=False)}")
    except Exception as e:
        print(f"[ERROR] fetch_all_data failed: {e}")
        return

    # 2) Učitaj današnje fixtures/odds iz cache-a
    today = date.today()
    fixtures_raw = read_json("fixtures.json", day=today)
    odds_raw = read_json("odds.json", day=today)

    fixtures = _normalize_items(fixtures_raw)
    odds = _normalize_items(odds_raw)

    if not fixtures:
        print("[WARN] No fixtures found for today after normalization. Aborting.")
        return

    if not odds:
        print("[WARN] No odds found for today after normalization. Aborting.")
        return

    print(f"[DATA] Fixtures={len(fixtures)} | Odds rows={len(odds)}")

    # 3) Build all ticket sets (LAYER 2)
    try:
        ticket_sets = build_all_ticket_sets(fixtures, odds)
    except Exception as e:
        print(f"[ERROR] build_all_ticket_sets failed: {e}")
        return

    # 3a) AI scoring meta-layer
    try:
        ticket_sets = annotate_ticket_sets_with_score(ticket_sets)
    except Exception as e:
        print(f"[WARN] annotate_ticket_sets_with_score failed: {e}")

    # 3b) Filter tickets by minimum score (62%)
    MIN_SCORE = 62.0
    filtered_sets = []
    for s in ticket_sets.get("sets", []):
        tickets = s.get("tickets", [])
        kept = [t for t in tickets if float(t.get("score", 0.0) or 0.0) >= MIN_SCORE]
        if kept:
            s = dict(s)
            s["tickets"] = kept
            filtered_sets.append(s)
    ticket_sets["sets"] = filtered_sets

    sets = ticket_sets.get("sets", [])
    total_tickets = sum(len(s.get("tickets", [])) for s in sets)
    print(f"[ENGINE] Built {len(sets)} sets after AI filter (score >= {MIN_SCORE}), total tickets={total_tickets}")

    # 4) Upis tickets.json za frontend / Pages
    try:
        write_tickets_json(ticket_sets)
        print("[OUTPUT] tickets.json written.")
    except Exception as e:
        print(f"[ERROR] write_tickets_json failed: {e}")

    # 5) Slanje tiketa na Telegram (ako je podešen chat id)
    if TELEGRAM_MORNING_CHAT_ID:
        for s in sets:
            status = s.get("status")
            if status and status not in ("OK", "PARTIAL"):
                # preskoči setove koji su označeni kao NO_DATA / ERROR itd.
                continue

            for t in s.get("tickets", []):
                text = _format_ticket_message(s, t)
                print(
                    f"[TELEGRAM] Sending ticket {t.get('ticket_id')} "
                    f"({s.get('code')}) to {TELEGRAM_MORNING_CHAT_ID}"
                )
                try:
                    send_message(
                        chat_id=TELEGRAM_MORNING_CHAT_ID,
                        text=text,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    print(f"[ERROR] Telegram send failed: {e}")

    print(f"[{datetime.utcnow().isoformat()}] Morning run done")


if __name__ == "__main__":
    main()
