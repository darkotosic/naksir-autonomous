# outputs/pages_writer.py
from __future__ import annotations

from pathlib import Path
from datetime import date
import json
from typing import Dict, Any

PUBLIC_DIR = Path(__file__).resolve().parent.parent / "public"


def _ensure_public_dir() -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)


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
        "date": date.today().isoformat(),
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
