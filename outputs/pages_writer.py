# outputs/pages_writer.py
from __future__ import annotations

from pathlib import Path
from datetime import date
import json
from typing import Dict, Any, List

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


def _ensure_public_dir() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)


def _summarize_ticket_sets(ticket_sets: Dict[str, Any]) -> Dict[str, Any]:
    """
    Deriviše osnovnu statistiku nad generisanim setovima/tiketima
    kako bi frontend imao jednostavan izvor istine.
    """

    sets: List[Dict[str, Any]] = []
    raw_sets = ticket_sets.get("sets")
    if isinstance(raw_sets, list):
        sets = [s for s in raw_sets if isinstance(s, dict)]

    tickets_total = 0
    status_counts: Dict[str, int] = {}

    for s in sets:
        status = str(s.get("status") or "").upper() or "UNKNOWN"
        status_counts[status] = status_counts.get(status, 0) + 1
        tickets_total += len(s.get("tickets", []) or [])

    return {
        "date": ticket_sets.get("date") or date.today().isoformat(),
        "generated_at": ticket_sets.get("generated_at"),
        "sets_total": len(sets),
        "tickets_total": tickets_total,
        "status_counts": status_counts,
    }


def write_tickets_json(ticket_sets: Dict[str, Any]) -> None:
    """
    Upisuje public/tickets.json u formatu:
    {
      "date": "YYYY-MM-DD",
      "sets": [...]
    }
    """
    _ensure_public_dir()

    data = {
        "date": ticket_sets.get("date") or date.today().isoformat(),
        "generated_at": ticket_sets.get("generated_at"),
        "analysis_mode": ticket_sets.get("analysis_mode"),
        "meta": ticket_sets.get("meta"),
        "summary": ticket_sets.get("summary") or _summarize_ticket_sets(ticket_sets),
        "engine_trace": ticket_sets.get("engine_trace", []),
        "sets": ticket_sets.get("sets", []),
    }
    fp = PUBLIC_DIR / "tickets.json"
    with fp.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def write_evaluation_json(evaluation: Dict[str, Any]) -> None:
    """
    Upisuje public/evaluation.json.

    Očekuje da evaluation već ima polja:
      - "date"
      - "generated_at"
      - "sets"
      - "summary"
    """
    _ensure_public_dir()

    fp = PUBLIC_DIR / "evaluation.json"
    with fp.open("w", encoding="utf-8") as f:
        json.dump(evaluation, f, ensure_ascii=False, indent=2)
