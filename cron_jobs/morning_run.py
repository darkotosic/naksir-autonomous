from __future__ import annotations

import os
import sys
import json
import logging
from datetime import datetime, date
from typing import Any, Dict, List

# Dodaj root projekta u sys.path (da core_data, builders itd. rade i u GitHub Actions)
ROOT_DIR = os.path.dirname(os.path.dirname(__file__))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)

from core_data.ingest import fetch_all_data
from core_data.cache import read_json
from builders.engine import build_ticket_sets
from ai_engine.meta import annotate_ticket_sets_with_score, get_adaptive_min_score
from ai_engine.in_depth import attach_in_depth_analysis
from outputs.pages_writer import write_tickets_json


def _load_cached_all_data(day: date) -> Dict[str, Any]:
    """
    Učitaj cache/<day>/all_data.json ako postoji, da AI layer ima
    kompletne podatke (fixtures, odds, standings, stats, h2h).
    """
    try:
        data = read_json("all_data.json", day=day)
        if isinstance(data, dict):
            print(
                f"[DEBUG] Loaded cached all_data.json for {day.isoformat()} "
                f"with keys={list(data.keys())}"
            )
            return data
        print(f"[WARN] all_data.json for {day.isoformat()} is not a dict, got {type(data)}")
    except FileNotFoundError:
        print(f"[WARN] all_data.json for {day.isoformat()} not found, will proceed without it.")
    except Exception as exc:
        print(f"[ERROR] Failed to read all_data.json for {day.isoformat()}: {exc}")

    return {}


def _debug_ticket_sets(ticket_sets: List[Dict[str, Any]]) -> None:
    """
    Lagani debug ispisi o tome šta je engine izgradio pre AI filtera.
    """
    print(f"[DEBUG] Ticket sets built: total_sets={len(ticket_sets)}")
    for s in ticket_sets:
        code = s.get("code")
        label = s.get("label")
        tickets = s.get("tickets") or []
        print(f"  - Set {code} | {label}: tickets={len(tickets)}")
        for t in tickets:
            tid = t.get("id")
            total_odds = t.get("total_odds")
            legs = t.get("legs") or []
            score = t.get("score")
            print(f"      Ticket {tid}: legs={len(legs)}, total_odds={total_odds}, score={score}")


def _debug_ai_scores(ticket_sets: List[Dict[str, Any]]) -> None:
    """
    Statistika AI score-ova (posle annotate_ticket_sets_with_score).
    """
    all_scores: List[float] = []
    for s in ticket_sets:
        for t in s.get("tickets") or []:
            ai_score = t.get("ai_score")
            if isinstance(ai_score, (int, float)):
                all_scores.append(float(ai_score))

    if not all_scores:
        print("[AI][DEBUG] No AI scores found on tickets.")
        return

    all_scores_sorted = sorted(all_scores)
    n = len(all_scores_sorted)
    median = all_scores_sorted[n // 2]
    print(
        f"[AI][DEBUG] Scores stats: count={n}, "
        f"min={all_scores_sorted[0]:.2f}, median={median:.2f}, max={all_scores_sorted[-1]:.2f}"
    )


def _filter_tickets_by_score(
    ticket_sets: List[Dict[str, Any]],
    adaptive_min_score: float,
) -> List[Dict[str, Any]]:
    """
    Filteruje tikete po adaptivnom min_score iz AI meta modela.
    Zadržava samo tikete sa ai_score >= adaptive_min_score.
    """
    filtered_sets: List[Dict[str, Any]] = []
    kept_count = 0
    dropped_count = 0

    print(f"[AI] Applying adaptive min_score filter: threshold={adaptive_min_score:.2f}")

    for s in ticket_sets:
        tickets = s.get("tickets") or []
        kept_tickets = []
        for t in tickets:
            ai_score = t.get("ai_score")
            if ai_score is None:
                ai_score = 0.0
            if ai_score >= adaptive_min_score:
                kept_tickets.append(t)
                kept_count += 1
            else:
                dropped_count += 1

        if kept_tickets:
            s2 = dict(s)
            s2["tickets"] = kept_tickets
            filtered_sets.append(s2)

    print(
        f"[AI] Filtering result: kept_tickets={kept_count}, "
        f"dropped_tickets={dropped_count}"
    )
    print(
        f"[AI] Sets before filter={len(ticket_sets)}, "
        f"after filter={len(filtered_sets)}"
    )

    return filtered_sets


def _serialize_for_pages(
    ticket_sets: List[Dict[str, Any]],
    day: date,
    ingest_summary: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Pripremi finalni payload za public/tickets.json:
    - meta (fixtures_total, odds_total, min_score, ...)
    - summary (broj setova, broj tiketa)
    - lista setova i tiketa
    """
    sets_total = len(ticket_sets)
    tickets_total = sum(len(s.get("tickets") or []) for s in ticket_sets)

    generated_at = datetime.utcnow().isoformat() + "Z"

    summary_block = {
        "date": day.isoformat(),
        "generated_at": generated_at,
        "sets_total": sets_total,
        "tickets_total": tickets_total,
    }

    meta_block = {
        "fixtures_count": ingest_summary.get("fixtures_total"),
        "odds_count": ingest_summary.get("odds_total"),
        "min_score": ingest_summary.get("min_score"),
        "raw_sets": ingest_summary.get("raw_sets"),
        "raw_total_tickets": ingest_summary.get("raw_total_tickets"),
        "sets_after_filter": sets_total,
        "tickets_after_filter": tickets_total,
        "generated_at": generated_at,
    }

    payload: Dict[str, Any] = {
        "date": day.isoformat(),
        "generated_at": generated_at,
        "meta": meta_block,
        "summary": summary_block,
        "sets": ticket_sets,
    }
    return payload


def main() -> None:
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )

    print("=" * 60)
    print(f"[{datetime.utcnow().isoformat()}] Morning run START")
    today = date.today()
    print(f"[INFO] Today: {today.isoformat()} (cache day)")

    # 1) Ingest svih podataka (LAYER 1)
    try:
        print("[INGEST] Calling fetch_all_data(days_ahead=2)...")
        ingest_summary = fetch_all_data(days_ahead=2)
        print("[INGEST] fetch_all_data completed.")
        try:
            print("[INGEST] Raw summary (truncated):")
            print(json.dumps(ingest_summary, indent=2, ensure_ascii=False)[:2000])
        except Exception:
            print("[INGEST] Could not pretty-print ingest_summary.")
    except Exception as exc:
        print(f"[FATAL] fetch_all_data failed: {exc}")
        raise

    # 2) Učitaj all_data.json (za AI scoring i in-depth analizu)
    all_data = _load_cached_all_data(today)

    # 3) Ticket engine (LAYER 2)
    print("[ENGINE] Building ticket sets...")
    ticket_sets = build_ticket_sets(today=today)
    _debug_ticket_sets(ticket_sets)
    print("[ENGINE] Ticket sets built.")

    # Za meta statistiku (raw_sets, raw_total_tickets)
    ingest_summary["raw_sets"] = len(ticket_sets)
    ingest_summary["raw_total_tickets"] = sum(
        len(s.get("tickets") or []) for s in ticket_sets
    )

    # 4) AI meta analiza / scoring (LAYER 3)
    print("[AI] Annotating ticket sets with AI score...")
    ticket_sets = annotate_ticket_sets_with_score(ticket_sets, all_data=all_data)
    _debug_ai_scores(ticket_sets)
    print("[AI] AI scores attached.")

    adaptive_min_score = get_adaptive_min_score(ticket_sets)
    ingest_summary["min_score"] = adaptive_min_score
    print(f"[AI] Adaptive min_score from model: {adaptive_min_score:.2f}")

    # 5) Filter po AI score
    ticket_sets = _filter_tickets_by_score(
        ticket_sets, adaptive_min_score=adaptive_min_score
    )

    # 6) In-depth analiza po legovima (LAYER 3 – detaljno)
    if all_data:
        print("[AI] Attaching in-depth analysis for each leg (where available)...")
        try:
            ticket_sets = attach_in_depth_analysis(ticket_sets, all_data)
            print("[AI] In-depth analysis attached.")
        except Exception as exc:
            print(f"[AI][WARN] attach_in_depth_analysis failed: {exc}")
    else:
        print("[AI][WARN] No all_data.json available, skipping in-depth analysis.")

    # 7) Finalni payload za GitHub Pages (LAYER 4 – output)
    payload = _serialize_for_pages(ticket_sets, today, ingest_summary)

    print("[OUTPUT] Writing tickets.json to public/ ...")
    write_tickets_json(payload)
    print("[OUTPUT] tickets.json updated.")

    print(f"[{datetime.utcnow().isoformat()}] Morning run DONE")
    print("=" * 60)


if __name__ == "__main__":
    main()
