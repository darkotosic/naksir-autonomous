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


# -----------------------------
# Helpers
# -----------------------------

def _normalize_items(raw: Any, label: str) -> List[Dict[str, Any]]:
    """
    Normalizuje fixtures/odds payload u listu dict-ova.
    Loguje tip i osnovne informacije da bismo videli problem ako je prazan.
    """
    print(f"[DEBUG] Normalizing {label}: type={type(raw).__name__}")

    if raw is None:
        print(f"[WARN] {label} raw is None.")
        return []

    if isinstance(raw, list):
        items = [x for x in raw if isinstance(x, dict)]
        print(f"[DEBUG] {label}: list with {len(items)} dict items.")
        return items

    if isinstance(raw, dict):
        # API-FOOTBALL stil: {"response": [...]}
        if "response" in raw and isinstance(raw["response"], list):
            items = [x for x in raw["response"] if isinstance(x, dict)]
            print(f"[DEBUG] {label}: dict with response[{len(items)}].")
            return items

        # već očišćena lista u nekom polju
        for key in ("items", "data", "rows"):
            val = raw.get(key)
            if isinstance(val, list):
                items = [x for x in val if isinstance(x, dict)]
                print(f"[DEBUG] {label}: dict with {key}[{len(items)}].")
                return items

        # fallback: jedan dict → lista od 1
        print(f"[DEBUG] {label}: single dict, wrapping into list[1].")
        return [raw]

    # ako je nešto neočekivano (string itd.)
    print(f"[WARN] {label}: unsupported raw type={type(raw)}. Returning empty list.")
    return []


def _preview_fixtures(fixtures: List[Dict[str, Any]], max_items: int = 5) -> None:
    print(f"[PREVIEW] Fixtures sample (up to {max_items}):")
    for i, fx in enumerate(fixtures[:max_items], start=1):
        league_name = fx.get("league_name") or fx.get("league", {}).get("name", "")
        league_country = fx.get("league_country") or fx.get("league", {}).get("country", "")
        home = fx.get("home") or fx.get("teams", {}).get("home", {}).get("name", "")
        away = fx.get("away") or fx.get("teams", {}).get("away", {}).get("name", "")
        kickoff = fx.get("kickoff") or fx.get("fixture", {}).get("date", "")
        print(f"  [{i}] {league_country} {league_name} | {home} vs {away} | {kickoff}")


def _preview_odds(odds: List[Dict[str, Any]], max_items: int = 5) -> None:
    print(f"[PREVIEW] Odds sample (up to {max_items}):")
    for i, row in enumerate(odds[:max_items], start=1):
        fixture_id = row.get("fixture_id") or row.get("fixture", {}).get("id")
        bookmaker = row.get("bookmaker") or row.get("bookmaker_name")
        market = row.get("market") or row.get("market_name")
        print(f"  [{i}] fixture_id={fixture_id} | bookmaker={bookmaker} | market={market}")


def _format_ticket_message(set_code: str, set_label: str, ticket: Dict[str, Any]) -> str:
    """
    Formatira jedan tiket za Telegram.
    """
    ticket_id = ticket.get("ticket_id", "N/A")
    total_odds = float(ticket.get("total_odds", 0.0) or 0.0)
    score = float(ticket.get("score", 0.0) or 0.0)

    lines: List[str] = []
    lines.append(f"🎫 {set_label} — Ticket {ticket_id}")
    lines.append(f"📅 {date.today().isoformat()}  |  Set: {set_code}")
    if total_odds > 0:
        lines.append(f"📈 Total odds: {total_odds:.2f}")
    lines.append(f"🤖 AI score: {score:.1f}%")
    lines.append("")

    for leg in ticket.get("legs", []):
        league_name = leg.get("league_name") or ""
        league_country = leg.get("league_country") or ""
        home = leg.get("home") or ""
        away = leg.get("away") or ""
        kickoff = leg.get("kickoff") or ""
        market = leg.get("market") or ""
        pick = leg.get("pick") or ""
        odds_val = float(leg.get("odds", 0.0) or 0.0)

        lines.append(f"🏟 {league_country} — {league_name}")
        lines.append(f"⚽ {home} vs {away}")
        lines.append(f"⏰ {kickoff}")
        lines.append(f"🎯 {market} → {pick} @ {odds_val:.2f}")
        lines.append("")

    return "\n".join(lines).strip()


# -----------------------------
# Main pipeline
# -----------------------------

def main() -> None:
    print("=" * 60)
    print(f"[{datetime.utcnow().isoformat()}] Morning run START")
    today = date.today()
    print(f"[INFO] Today: {today.isoformat()} (cache day)")

    # 1) Ingest svih podataka (LAYER 1)
    try:
        ingest_summary = fetch_all_data(days_ahead=2)
        print("[INGEST] fetch_all_data completed.")
        try:
            print("[INGEST] Raw summary:")
            print(json.dumps(ingest_summary, indent=2, ensure_ascii=False)[:2000])
        except Exception:
            print("[INGEST] (summary not JSON-serializable)")
    except Exception as e:
        print(f"[ERROR] fetch_all_data failed: {e}")
        return

    # 2) Učitaj fixtures i odds iz cache-a
    fixtures_raw = read_json("fixtures.json", today)
    odds_raw = read_json("odds.json", today)

    if fixtures_raw is None:
        print("[ERROR] fixtures.json for today not found in cache. Aborting.")
        return
    if odds_raw is None:
        print("[ERROR] odds.json for today not found in cache. Aborting.")
        return

    fixtures = _normalize_items(fixtures_raw, "fixtures")
    odds = _normalize_items(odds_raw, "odds")

    print(f"[DATA] Fixtures count={len(fixtures)} | Odds rows count={len(odds)}")

    if not fixtures:
        print("[ERROR] No fixtures after normalization. Aborting.")
        return
    if not odds:
        print("[ERROR] No odds after normalization. Aborting.")
        return

    _preview_fixtures(fixtures)
    _preview_odds(odds)

    # 3) Build all ticket sets (LAYER 2)
    try:
        ticket_sets = build_all_ticket_sets(fixtures, odds)
    except Exception as e:
        print(f"[ERROR] build_all_ticket_sets failed: {e}")
        return

    sets = ticket_sets.get("sets", []) or []
    total_tickets_raw = sum(len(s.get("tickets", [])) for s in sets)
    print(f"[ENGINE] Raw sets={len(sets)}, raw total tickets={total_tickets_raw}")
    for s in sets:
        print(
            f"[ENGINE] Set {s.get('code')} | status={s.get('status')} | "
            f"tickets={len(s.get('tickets', []))}"
        )

    # 3a) AI scoring (LAYER 3)
    try:
        ticket_sets = annotate_ticket_sets_with_score(ticket_sets)
    except Exception as e:
        print(f"[WARN] annotate_ticket_sets_with_score failed: {e}")

    # 3b) Filter po AI score >= 62
    MIN_SCORE = 62.0
    filtered_sets: List[Dict[str, Any]] = []
    for s in ticket_sets.get("sets", []) or []:
        tickets = s.get("tickets", [])
        kept = []
        for t in tickets:
            score = float(t.get("score", 0.0) or 0.0)
            if score >= MIN_SCORE:
                kept.append(t)
            else:
                print(
                    f"[FILTER] Dropped ticket {t.get('ticket_id')} from set {s.get('code')} "
                    f"due to low score={score:.1f} (< {MIN_SCORE})"
                )
        if kept:
            s2 = dict(s)
            s2["tickets"] = kept
            filtered_sets.append(s2)

    ticket_sets["sets"] = filtered_sets

    sets_after = ticket_sets.get("sets", []) or []
    total_tickets_after = sum(len(s.get("tickets", [])) for s in sets_after)
    print(
        f"[ENGINE] After AI filter (score >= {MIN_SCORE}) "
        f"sets={len(sets_after)}, total tickets={total_tickets_after}"
    )
    for s in sets_after:
        print(
            f"[ENGINE] Kept set {s.get('code')} | status={s.get('status')} | "
            f"tickets={len(s.get('tickets', []))}"
        )

    if not sets_after:
        print("[WARN] No ticket sets left after AI filter. tickets.json will be empty 'sets':[].")

    # 4) Upis tickets.json za frontend / Pages (LAYER 4)
    try:
        write_tickets_json(ticket_sets)
        print("[OUTPUT] tickets.json written to public/ directory.")
    except Exception as e:
        print(f"[ERROR] write_tickets_json failed: {e}")

    # 5) Slanje tiketa na Telegram (ako je podešen chat id)
    if TELEGRAM_MORNING_CHAT_ID and sets_after:
        print(f"[TELEGRAM] Sending tickets to chat={TELEGRAM_MORNING_CHAT_ID}")
        for s in sets_after:
            status = s.get("status")
            if status and status not in ("OK", "PARTIAL"):
                print(f"[TELEGRAM] Skipping set {s.get('code')} due to status={status}")
                continue

            set_code = s.get("code", "N/A")
            set_label = s.get("label", "N/A")
            for ticket in s.get("tickets", []):
                text = _format_ticket_message(set_code, set_label, ticket)
                print(
                    f"[TELEGRAM] Sending ticket {ticket.get('ticket_id')} from set {set_code} "
                    f"with score={ticket.get('score')}"
                )
                try:
                    send_message(
                        chat_id=TELEGRAM_MORNING_CHAT_ID,
                        text=text,
                        parse_mode="Markdown",
                    )
                except Exception as e:
                    print(f"[ERROR] Telegram send failed: {e}")
    else:
        if not TELEGRAM_MORNING_CHAT_ID:
            print("[TELEGRAM] TELEGRAM_MORNING_CHAT_ID not set, skipping Telegram step.")
        if not sets_after:
            print("[TELEGRAM] No tickets after AI filter, nothing to send.")

    print(f"[{datetime.utcnow().isoformat()}] Morning run DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
