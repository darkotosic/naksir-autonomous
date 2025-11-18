# evaluation/engine.py
from __future__ import annotations

from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional

from core_data.api_client import fetch_fixtures_by_date
from core_data.cleaners import clean_fixtures
from outputs.pages_writer import write_evaluation_json


PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


def _load_tickets_for_date(target_date: date) -> Optional[Dict[str, Any]]:
    """
    Učitava public/tickets.json i proverava da li odgovara target_date.
    Ako ne odgovara, ipak vraća data (ali zabeležiš to u logu u praksi).
    """
    fp = PUBLIC_DIR / "tickets.json"
    if not fp.exists():
        return None
    with fp.open("r", encoding="utf-8") as f:
        data = json.load(f)
    # date u fajlu je informativan – može da bude od juče dok radiš eval sutra
    return data


def _index_fixtures_by_id(fixtures: List[Dict[str, Any]]) -> Dict[int, Dict[str, Any]]:
    idx: Dict[int, Dict[str, Any]] = {}
    for fx in fixtures:
        fixture = fx.get("fixture") or {}
        fid = fixture.get("id")
        if fid is not None:
            idx[int(fid)] = fx
    return idx


def _resolve_leg_result(leg: Dict[str, Any], fx: Dict[str, Any]) -> str:
    """
    Vraća: '✅', '❌' ili '⏳' (ako fixture nije završen / nema rezultata).
    """
    goals = fx.get("goals") or {}
    score = fx.get("score") or {}
    status = (fx.get("fixture") or {}).get("status") or {}
    status_short = status.get("short")

    # ako nije FT (završeno), tretiramo kao ⏳
    if status_short not in ("FT", "AET", "PEN"):
        return "⏳"

    home = goals.get("home")
    away = goals.get("away")
    if home is None or away is None:
        return "⏳"

    total = (home or 0) + (away or 0)
    market = leg.get("market")

    if market == "O25":
        return "✅" if total >= 3 else "❌"
    if market == "U35":
        return "✅" if total <= 3 else "❌"
    if market == "HOME":
        return "✅" if home > away else "❌"
    if market == "BTTS":
        return "✅" if home > 0 and away > 0 else "❌"
    if market == "DC_1X":
        return "✅" if home >= away else "❌"
    if market == "DC_X2":
        return "✅" if away >= home else "❌"
    if market == "HT_O05":
        ht = (score.get("halftime") or {})
        ht_home = ht.get("home")
        ht_away = ht.get("away")
        if ht_home is None or ht_away is None:
            return "⏳"
        ht_total = (ht_home or 0) + (ht_away or 0)
        return "✅" if ht_total >= 1 else "❌"

    # default – ako ne znamo market
    return "⏳"


def _evaluate_ticket(
    ticket: Dict[str, Any],
    fixture_index: Dict[int, Dict[str, Any]],
) -> Dict[str, Any]:
    legs = ticket.get("legs", [])
    any_pending = False
    any_fail = False

    evaluated_legs: List[Dict[str, Any]] = []

    for leg in legs:
        fid = leg.get("fixture_id")
        fx = fixture_index.get(int(fid)) if fid is not None else None
        if fx is None:
            result = "⏳"
        else:
            result = _resolve_leg_result(leg, fx)

        leg_copy = dict(leg)
        leg_copy["result"] = result
        evaluated_legs.append(leg_copy)

        if result == "⏳":
            any_pending = True
        elif result == "❌":
            any_fail = True

    if any_fail:
        ticket_result = "LOSE"
    elif any_pending:
        ticket_result = "PENDING"
    else:
        ticket_result = "WIN"

    out = dict(ticket)
    out["legs"] = evaluated_legs
    out["result"] = ticket_result
    return out


def run_daily_evaluation(target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Glavni evaluation job: koristi se u cron_jobs/evaluation_run.py.

    Tipično: target_date = jučerašnji datum.
    """
    import json  # lokalni import da izbegnemo konflikte

    if target_date is None:
        target_date = date.today() - timedelta(days=1)

    target_str = target_date.isoformat()

    # 1) Učitaj tickets.json
    fp = PUBLIC_DIR / "tickets.json"
    if not fp.exists():
        raise FileNotFoundError("tickets.json not found in public/")

    with fp.open("r", encoding="utf-8") as f:
        tickets_data = json.load(f)

    # 2) Povuci fixtures za target_date sa API-FOOTBALL i očisti
    raw_fx = fetch_fixtures_by_date(target_str)
    fixtures = clean_fixtures(raw_fx)
    fixture_index = _index_fixtures_by_id(fixtures)

    # 3) Evaluacija po setovima i tiketima
    sets_out: List[Dict[str, Any]] = []
    win = lose = pending = 0

    for s in tickets_data.get("sets", []):
        set_code = s.get("code")
        set_label = s.get("label")
        tickets = s.get("tickets", [])

        evaluated_tickets: List[Dict[str, Any]] = []
        for t in tickets:
            et = _evaluate_ticket(t, fixture_index)
            evaluated_tickets.append(et)

            if et["result"] == "WIN":
                win += 1
            elif et["result"] == "LOSE":
                lose += 1
            elif et["result"] == "PENDING":
                pending += 1

        sets_out.append(
            {
                "code": set_code,
                "label": set_label,
                "tickets": evaluated_tickets,
            }
        )

    total = win + lose + pending
    summary = {
        "date": target_str,
        "tickets_total": total,
        "tickets_win": win,
        "tickets_lose": lose,
        "tickets_pending": pending,
    }

    evaluation = {
        "date": target_str,
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "sets": sets_out,
        "summary": summary,
    }

    # 4) Upis evaluation.json
    write_evaluation_json(evaluation)
    return evaluation
